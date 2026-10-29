"""Bounded process-pool execution of independent tasks (simulation and model runs).

Workers only compute; every result is handed back to the parent process, which alone
writes files. Each task must be fully determined by its own seed and inputs, so results
do not depend on the worker count or on the order in which tasks finish.
"""

from __future__ import annotations

import itertools
import multiprocessing
import os
import time
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait

from radiosensitivity_ml.models.checkpoints import THREAD_VARIABLES

# Set once per worker process by the pool initializer; read only by _worker_call.
_WORKER: tuple[Callable[[object, object], object], object] | None = None


def _init_worker(run: Callable[[object, object], object], context: object) -> None:
    global _WORKER
    _WORKER = (run, context)


def _timed(
    run: Callable[[object, object], object], context: object, task: object
) -> tuple[object, float]:
    started = time.monotonic()
    value = run(context, task)
    return value, time.monotonic() - started


def _worker_call(task: object) -> tuple[object, float]:
    if _WORKER is None:
        raise RuntimeError("worker process was not initialised")
    return _timed(_WORKER[0], _WORKER[1], task)


def thread_settings() -> dict[str, str | None]:
    """The BLAS/OpenMP thread variables of this process's environment."""
    return {name: os.environ.get(name) for name in THREAD_VARIABLES}


def check_workers(workers: int) -> None:
    """Validate the worker count and, for workers > 1, the BLAS thread settings.

    Each worker must use one BLAS/OpenMP thread (no oversubscription), and the parent must
    use the same setting so that serial and parallel sessions compute identically. The
    settings are read from the environment (recorded in, and compared by, run manifests).
    """
    available = os.cpu_count() or 1
    if not 1 <= workers <= available:
        raise ValueError(f"workers must be between 1 and {available} (logical cores)")
    if workers > 1:
        found = thread_settings()
        if any(value != "1" for value in found.values()):
            raise ValueError(
                f"--workers {workers} requires {', '.join(THREAD_VARIABLES)} = 1 in the "
                f"environment (found {found}); export them before every session of a run"
            )


def execute_tasks(
    tasks: Iterable[object],
    run: Callable[[object, object], object],
    context: object,
    workers: int,
    handle: Callable[[object, object, float], None],
    max_pending: int | None = None,
) -> None:
    """Call ``run(context, task)`` for every task and ``handle(task, value, seconds)`` on
    each result, in THIS process only (so only the parent writes files).

    workers == 1: in this process, in task order. workers > 1: a spawn-context process
    pool; ``run`` and ``context`` reach each worker once (initializer), never per task;
    at most ``max_pending`` (default 2 x workers) tasks are submitted at a time. Results
    are handled in completion order, so ``handle`` must not depend on that order. On a
    task error or Ctrl+C, queued tasks are cancelled, nothing more is handled and the
    exception propagates; files already written by ``handle`` are untouched.
    """
    if workers == 1:
        for task in tasks:
            value, seconds = _timed(run, context, task)
            handle(task, value, seconds)
        return
    limit = max_pending or 2 * workers
    queue = iter(tasks)
    pool = ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=_init_worker,
        initargs=(run, context),
    )
    pending: dict[Future, object] = {}
    try:
        while True:
            for task in itertools.islice(queue, limit - len(pending)):
                pending[pool.submit(_worker_call, task)] = task
            if not pending:
                break
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                task = pending.pop(future)
                value, seconds = future.result()
                handle(task, value, seconds)
    except BaseException:
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
