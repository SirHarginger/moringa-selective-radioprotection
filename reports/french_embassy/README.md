# French Embassy project report

| File | What it is |
|---|---|
| `report.md` | The report source. The single editable document; everything else is generated or referenced. |
| `references.bib` | Bibliography. Every entry verified against Crossref or Europe PMC, with the route and reading depth in its `note` field. |
| `figure_manifest.csv` | Figure number → rendered file → full caption. Written by `scripts/make_report_figures.py`. |
| `table_manifest.csv` | Table number → file → producing script → generation status. |
| `build.sh` | Builds `outputs/final_project_report.pdf` and `.docx` with pandoc. Refuses to build if a referenced figure is missing. |
| `latex/` | Typeset LaTeX edition generated from `report.md` (which stays authoritative): `bash reports/french_embassy/latex/build.sh` writes `outputs/final_project_report_latex.pdf`. See `latex/README.md`. |
| `outputs/` | Built documents. **Empty until `build.sh` is run.** |

## Status, stated plainly

The **report text is complete** and every number in it comes from a saved output of the
completed primary run, verified at the time of writing.

The following have **not** been executed, and the report does not present them as results:

| Output | Why not |
|---|---|
| Compound tables C1–C4 and the ranked shortlist | A project rule reserves pipeline execution to the investigator |
| Report figures (PNG/PDF) | Same; also requires `seaborn`, which is not yet installed |
| `final_project_report.pdf` / `.docx` | Depends on the figures above |
| Coverage simulation and negative controls | Deferred by recorded protocol deviation (D04.06) |

## Ordered execution sequence

**The whole workflow in one command** (everything except the overnight negative controls):

```bash
conda activate explainable-radiosensitivity-ml
bash scripts/run_full_workflow.sh --list      # stages, dependencies and measured costs
bash scripts/run_full_workflow.sh             # ~30 min at six workers
bash scripts/run_full_workflow.sh --all       # adds the ~10-20 h negative-control run
```

Each stage is re-runnable and skips work that already exists, so an interrupted workflow
can simply be restarted. The stages are also listed individually below, in case you prefer
to drive them by hand.

Run from the repository root, in this order. Steps 1–2 are prerequisites; steps 3–6
produce the deliverables.

```bash
# 0. Activate the project environment
conda activate explainable-radiosensitivity-ml

# 1. Install the one new dependency (the report figures use seaborn)
conda install -c conda-forge seaborn        # or: pip install 'seaborn==0.13.2'

# 2. Apply the pending cosmetic formatting, then check the tree is clean
ruff format src scripts tests
ruff check src scripts tests
git status --porcelain                      # analysis runs refuse a dirty tree

# 3. Run the tests (none of these fit a model)
pytest -m 'not model_fit' -q
#    Optional, slower, fits models on synthetic fixtures only:
# pytest -m model_fit -q

# 4. Publication tables (already generated once; skip unless regenerating)
# python scripts/make_publication_tables.py --config configs/publication.yaml
# python scripts/make_publication_tables.py --config configs/publication.yaml --part triage

# 5. Exploratory modelling, all on the frozen primary's splits (primary_v1 untouched)
python scripts/verify_run_consistency.py --reference primary_v1 \
    --candidate exploratory_m3_v1 --pre                       # config-level vetting
python scripts/run_model.py --config configs/experiment_exploratory_m3.yaml --workers 6
python scripts/run_model.py --config configs/experiment_loto.yaml --workers 6
python scripts/run_model.py --config configs/experiment_scales.yaml --workers 6
python scripts/verify_run_consistency.py --reference primary_v1 \
    --candidate exploratory_m3_v1                             # full verification
python scripts/evaluate_models.py --config configs/experiment_exploratory_m3.yaml
python scripts/evaluate_models.py --config configs/experiment_loto.yaml
python scripts/evaluate_models.py --config configs/experiment_scales.yaml

# 5b. OPTIONAL, ~10-20 h: negative controls, 1000 draws of each null. Resumable.
#     Read docs/robustness_plan.md section 2 FIRST: this does not by itself license
#     tier A/B or a p-value for the primary comparison.
python scripts/run_model.py --config configs/experiment_controls.yaml --workers 6
python scripts/evaluate_models.py --config configs/experiment_controls.yaml
python scripts/run_explainability.py --config configs/experiment_controls.yaml --workers 6
python scripts/generate_triage.py --config configs/triage_controls.yaml

# 6. Explainability for eligible new runs (primary_v1's is complete and is NOT recomputed)
python scripts/run_explainability.py \
    --config configs/experiment_exploratory_m3.yaml --workers 6

# 7. Compound evidence and candidate ranking  -> results/tables/primary_v1/compounds_v1/
python scripts/make_compound_tables.py --config configs/compounds.yaml

# 8. Report figures -> figures/png/, figures/pdf/, figures/metadata/ + figure_manifest.csv
python scripts/make_report_figures.py --config configs/figures_report.yaml

# 9. Audit every output and its provenance before writing anything into the report
python scripts/audit_outputs.py

# 10. Build the report -> reports/french_embassy/outputs/
bash reports/french_embassy/build.sh
```

### If a step fails

- **Step 5**, `table_c4` cannot be built: the Hallmark GMT or the triage table is missing.
  Use `--no-overlap` to produce C1–C3 without the pathway-overlap table.
- **Step 5 or 6**, `FileExistsError`: outputs are write-once. Bump `version` in the
  configuration, or pass `--overwrite` to `make_report_figures.py` to reproduce figures in
  place.
- **Step 6**, `CurationError` or `FigureInputError`: the message names the offending record,
  column or path. Nothing is written until every figure has been built, so a failure leaves
  the output folders untouched.
- **Step 7**, missing figure: run step 6 first. The build deliberately refuses to produce a
  report with absent figures.
- **Step 7**, APA style: download `apa.csl` into this folder (one-line command in
  `build.sh`); without it the build proceeds in pandoc's default author-date style.

## Before submission

1. Optionally add an `author:` block to the YAML header of `report.md` (investigator,
   institution) to print names on the cover. **No administrative detail has been
   invented**; there is no funding programme, reference number, partnership or approval
   status in this report.
2. Close the open evidence items in `docs/compound_evidence_curation.md` §8 — in particular
   the ambiguous glucomoringin identifier, the missing radiation doses and concentrations,
   the unread Heliyon erratum, and the retraction re-check for one journal.
3. Confirm the Hallmark GMT's source identity against the official URL (`data/manifests/`).
4. Re-read §9 (Limitations) and confirm you are content to publish each one as written.
5. Check that the CLARIFi data DOI **and** its CC BY-NC 4.0 licence are cited, as the
   licence requires.
