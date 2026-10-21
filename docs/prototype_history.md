# Prototype history

The repository began as a prototype titled "moringa-selective-radioprotection". It was committed as `76f9e6f` ("initial commit", 2026-10-20). **It is not ground truth and not the specification for Explainable Radiosensitivity ML.** Its methods and preliminary numbers have not been reviewed or reproduced, and nothing from it carries over.

## Archive

| Item | Value |
|---|---|
| Archived commit | `76f9e6f30042c55b22ef44e8ef1973ea0dadbc50` |
| Local archive tag | `archive/pre-radiosensitivity-ml` (annotated, local only, not pushed) |
| Verification | `docs/phase_00_verification.md` §5 |

### Recovery

Inspect any file without changing the working tree:

```
git show archive/pre-radiosensitivity-ml:config/analysis.yaml
git ls-tree --name-only -r archive/pre-radiosensitivity-ml
```

Check out the whole prototype in a separate folder, without touching this one:

```
git worktree add ../prototype-archive archive/pre-radiosensitivity-ml
```

The prototype is **not** restored into the active research structure.

## What the prototype was

A plan to rank natural products for possible selective radioprotection. It started with predicting NCI-60 compound potency (−log₁₀ GI₅₀) for MCF-7 and DU145 from chemical fingerprints. Later planned stages were:

- normal-cell compatibility;
- radiation-response transcriptomics;
- a weighted composite score;
- COCONUT natural-product screening;
- a Moringa phytochemical enrichment test.

This is a **different question** from the current aim, which is predicting cell-line radiosensitivity (clonogenic SF2) across datasets and cancer types. Compound GI₅₀ measures drug potency, not radiosensitivity.

## What it contained (in `76f9e6f`)

- `src/moringa_radioprotection/`: `nci.py`, `raw_activity.py`, `modeling.py`, `models.py`, `analysis.py`, `chemistry.py`, `plotting.py`, plus empty stubs.
- `scripts/`:
  - non-empty: `fetch_nci.py`, `prepare_nci.py`, `analyze_nci.py`, `audit_nci_raw.py`, `prepare_cancer_modeling.py`, `train_cancer.py`;
  - empty stubs: `interpret_candidates.py`, `prepare_coconut.py`, `prepare_normal.py`, `prepare_radiation.py`, `rank_candidates.py`, `screen_coconut.py`, `validate_external.py`.
- `tests/`: four test modules.
- `config/analysis.yaml`: NCI CellMiner download URLs, scaffold-split fractions, model grids.
- `docs/latex/`: a progress report, with LaTeX build artefacts. It reports preliminary, unfinished benchmark metrics, which are not reproduced here and must not be cited.
- `docs/research_plan.md` (empty) and `requirements.txt` (empty).
- `graphify-out/`: an auto-generated code-graph cache.

## Status in the working tree

These files were deleted from the working tree on 2026-10-20. The deletion is **not committed**; committing it is proposal P00.01 in `docs/decision_log.md`.

Also retired from the working tree in phase_00 (uncommitted deletions; originals in the archive tag):
- `Makefile` and the empty `requirements.txt` (D00.21);
- `results/figures/` and `results/screening/` (D00.22).

Still present, marked LEGACY:
- prototype packages listed in `environment.yml` (decisions deferred; see the decision log);
- `graphify-out/` entries still in the git index (untracking is P00.06).

## Former README commands (preserved verbatim; the scripts no longer exist in the working tree; the environment was then called `moringa-rad`)

```
conda activate moringa-rad

python scripts/fetch_nci.py --config config/analysis.yaml
python scripts/prepare_nci.py --config config/analysis.yaml
python scripts/analyze_nci.py --config config/analysis.yaml
python scripts/audit_nci_raw.py --config config/analysis.yaml
python scripts/prepare_cancer_modeling.py --config config/analysis.yaml
python scripts/train_cancer.py --config config/analysis.yaml

python scripts/train_cancer.py --config config/analysis.yaml --resume
```

## Possible future use

The research-director suggests the compound-potency work could be revisited after phase_05 as an explicitly separate, secondary aim. This is a recommendation only (`docs/decision_log.md` O00.08).
