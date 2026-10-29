# figures/

## Layout

```text
figures/
├── specs/        one tracked YAML specification per planned figure or table (TRACKED)
├── png/          rendered report figures, 600 dpi raster   (gitignored)
├── pdf/          rendered report figures, vector           (gitignored)
├── metadata/     provenance sidecars + figure_index.csv    (gitignored)
└── generated/    version-1 and version-2 figures, legacy layout (gitignored)
```

- **`png/`, `pdf/`, `metadata/`** hold the **version-3 report figures** (D05.02). The
  basename is identical in all three folders: `fig_03_model_performance.png`,
  `fig_03_model_performance.pdf`, `fig_03_model_performance.meta.json`. Only PNG and PDF
  are produced; **SVG is refused** by the renderer, and a test enforces that.
  `metadata/figure_index.csv` lists every rendered figure with its report number and
  paths.
- **`generated/`** holds the earlier version-1 and version-2 figures in the previous
  single-folder, three-format layout. **Nothing in it was deleted.** It is preserved
  because those files are the reproducibility record of the figures described in the
  decision log, and because `configs/figures.yaml`, `configs/figures_v2.yaml`,
  `configs/figures_triage_v2.yaml` and `configs/diagrams.yaml` still write there through
  `scripts/generate_figures.py`. The legacy SVG outputs in that folder may be excluded
  from the final deliverable; they are not read by any workflow.
- **`specs/`** stays tracked. Write the spec before the code.

## Producing figures

```bash
# version-3 report figures -> png/, pdf/, metadata/
python scripts/make_report_figures.py --config configs/figures_report.yaml
python scripts/make_report_figures.py --config configs/figures_report.yaml --only fig_08 fig_09
python scripts/make_report_figures.py --config configs/figures_report.yaml --overwrite

# legacy version-1/version-2 figures and diagrams -> generated/
python scripts/generate_figures.py --config configs/figures_v2.yaml
```

Report figures are write-once unless `--overwrite` is given, which is a *reproduction* of
a deterministic figure from immutable saved tables, not a new result. Legacy figures are
write-once with no override: bump `version` in their config instead.

## Rules for report figures

Code lives in `src/radiosensitivity_ml/visualization/` — `style.py` (one shared visual
identity), `report_figures.py` (Seaborn figure functions), `report_render.py` (output
layout and provenance), `diagrams.py` (conceptual diagrams). Never in this folder.

A report figure carries **no title, no figure number, no footnote and no explanatory
note**. Captions, methodological notes and limitations live in
`configs/figures_report.yaml` and in the report, and a test checks that the two agree
exactly so they cannot drift apart. Only short text is allowed on a figure: lowercase
bold panel letters, value labels and short series labels. Text is at least 8 pt at final
size, and figures are drawn at the A4 text width (160 mm).

Every figure reads **saved tables only**; nothing is refitted or re-predicted. Inputs
under `tests/` are refused, so a synthetic fixture can never be plotted here. Statistical
rules (one point per independent biological component, bars from zero, symmetric
difference axes, no fitted trend lines, no unvalidated intervals, no clustering) are
documented in `report_figures.py` and enforced by `tests/test_report_figures.py`.

Full conventions: `docs/figure_standards.md`. Synthetic test fixtures must never produce
files in this folder.
