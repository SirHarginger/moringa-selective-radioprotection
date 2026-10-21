# Figure standards

Status: phase_00. No figures or manuscript tables exist. These standards apply to all future figure code (`.claude/rules/plotting.md`, `publication-figures` skill). Journal-specific numbers are typical values; check them against the target journal's author guide once it is chosen.

## 1. Identifiers and file names

| Item | Pattern | Example |
|---|---|---|
| Main figure ID | `fig_NN` | `fig_01` |
| Supplementary figure ID | `fig_sNN` | `fig_s01` |
| Figure spec | `figures/specs/fig_NN_<slug>.yaml` | `figures/specs/fig_01_sf2_by_tissue.yaml` |
| Figure entry point | `scripts/make_fig_NN_<slug>.py` | `scripts/make_fig_01_sf2_by_tissue.py` |
| Rendered figure | `figures/generated/fig_NN_<slug>_vN.{pdf,svg,png}` | `fig_01_sf2_by_tissue_v1.pdf` |
| Separately exported panel | `fig_NNa_<slug>_vN.*` | `fig_01a_sf2_by_tissue_v1.pdf` |
| Provenance sidecar | same stem + `.meta.json` | `fig_01_sf2_by_tissue_v1.meta.json` |
| Main / supplementary table ID | `table_NN` / `table_sNN` | `table_01` |
| Table spec | `figures/specs/table_NN_<slug>.yaml` (one spec folder) | `figures/specs/table_01_cohort_summary.yaml` |
| Table output | `results/tables/table_NN_<slug>_vN.csv` + `.meta.json` | `table_01_cohort_summary_v1.csv` |

- Slugs are lowercase `snake_case`. `vN` is the spec's `spec_version`.
- IDs are permanent once assigned and are never renumbered silently. If manuscript order changes, record the mapping in the spec (`manuscript_label`).
- Supporting tables in `results/tables/` that are not manuscript tables carry no `table_` prefix.

## 2. Every figure starts with a specification

Before any figure code, copy `figures/specs/_template.yaml`. The spec states:

- the scientific question;
- one named endpoint and assay;
- data sources (manifest IDs and checksums);
- n per group, with its unit;
- the units on every axis;
- the comparison shown;
- the uncertainty statistic and method;
- which held-out split the predictions come from;
- layout, outputs, a draft caption, and status.

## 3. Typography and sizes (at final print size)

- **Font:** sans-serif (Arial or Helvetica; DejaVu Sans as fallback), the same in every figure.
- **Sizes:** text 8 pt minimum (project rule). Panel letters 9 pt bold, lowercase (a, b, c), at the top left.
- **Widths:** draw at final width, never by rescaling. Typical widths, to verify per journal:
  - single column about 85–90 mm;
  - 1.5 column about 140 mm;
  - double column about 180–190 mm;
  - maximum height about 240 mm.
- **Lines:** data lines 0.75–1.0 pt, axes and ticks 0.5–0.6 pt, markers 3–4 pt.
- **Clutter:** no top or right spines unless needed. No 3D, shadows or decorative gridlines.

## 4. Labels, units, uncertainty and n

- Axis labels use the form "Quantity (unit)". Examples:
  - "Dose (Gy)"
  - "Surviving fraction at 2 Gy (SF2)"
  - "Optical density (OD, wavelength nm)"
  - "log₂ fold change"
- Dimensionless quantities get no unit.
- **Never put different endpoints on one axis.** SF2, viability, optical-density or crystal-violet proliferation, PEF and expression stay separate.
- Every caption states:
  - the statistic shown (SD, SEM or 95% CI);
  - how it was computed (e.g. bootstrap with B resamples and a recorded seed);
  - the unit of n (cell lines, biological replicates or independent experiments).
- Show n in the panel or the caption, for every group.

## 5. Observed vs predicted

- **Observed:** filled markers, solid lines.
- **Predicted:** open markers, dashed lines, labelled with the held-out fold or dataset.
- Parity and calibration plots use equal axis ranges and a y = x reference line.
- Captions say whether values are observations or model predictions, and from which split.

## 6. Colour and accessibility

- **Categorical default, Okabe–Ito:** `#000000` `#E69F00` `#56B4E9` `#009E73` `#F0E442` `#0072B2` `#D55E00` `#CC79A7`. Avoid `#F0E442` for thin lines on white.
- **Alternative, Paul Tol "bright":** `#4477AA` `#EE6677` `#228833` `#CCBB44` `#66CCEE` `#AA3377` `#BBBBBB`.
- **Continuous:** viridis or cividis.
- **Diverging:** a Paul Tol diverging scheme. Check its hex codes against Tol's technical note before hard-coding them.
- **Grayscale rule:** colour is never the only cue. Pair groups with marker shape or line style. A style test will check grayscale luminance separation; the threshold is to be set in phase_03.

## 7. Export

- **Formats:** PDF and SVG (vector), plus PNG at 300 dpi for data plots and 600 dpi for line art.
- **Matplotlib settings:** `pdf.fonttype: 42`, `ps.fonttype: 42`, `svg.fonttype: "none"`, fixed metadata (no creation date) for reproducible builds.
- **Sidecar** (`.meta.json`) records:
  - script path, git commit and dirty flag;
  - config path and SHA-256;
  - SHA-256 of every input table, and the run-record ID;
  - seeds, package versions, UTC timestamp;
  - `data_provenance` (`empirical`, `synthetic_fixture` or `conceptual_diagram`).
- **Conceptual diagrams** (`src/radiosensitivity_ml/visualization/diagrams.py`, `configs/diagrams.yaml`) contain no data, predictions or statistics; PNG at 600 dpi (line art). They are drawn in millimetre coordinates at final width, and a layout test checks that every label fits its box. Any diagram that depicts implemented rules must take its text from the code (as fig_s04 does from `triage.rules.criteria_text`).

## 8. Where things live

| What | Where | Git |
|---|---|---|
| Style constants, export helper, plotting functions | `src/radiosensitivity_ml/visualization/` | Tracked |
| Figure entry points | `scripts/make_fig_NN_*.py` | Tracked |
| Figure and table specs | `figures/specs/` | Tracked |
| Rendered figures and sidecars | `figures/generated/` (the only figure output location) | Ignored |
| Manuscript tables and supporting tables | `results/tables/` | Ignored |
| Final copies for submission | `manuscript/` | Decided in phase_05 |

The prototype folder `results/figures/` was retired in phase_00 (`docs/decision_log.md` D00.22).

## 9. Synthetic fixtures never reach the manuscript

- Fixtures live only in `tests/fixtures/`, are named `SYNTHETIC_*` and are labelled "SYNTHETIC - TEST ONLY".
- Test plots go to pytest's temporary folder and are watermarked "SYNTHETIC".
- Plotting entry points refuse inputs under `tests/` and inputs without a manifest entry with matching checksums.
- A phase_03 check fails if `figures/generated/` or `manuscript/` contains any output without a sidecar, or with `data_provenance: synthetic_fixture`.
- Style tests inspect figure configuration only. They never compute scientific results.

## 10. Captions

Captions are drafted in the spec and finalised from the run record. Each caption includes:

- what is shown (observed or predicted);
- the endpoint and assay;
- n and its unit;
- the error statistic and method;
- the data source and release;
- any exclusions.

*Reviewed in phase_00 by the figure-editor agent, using the `publication-figures` skill.*
