# Phase 01 dataset feasibility assessment

**Status:** phase_01 draft for investigator review, 2026-10-21.

**Prepared by:**
- radiogenomics-curator subagent (source verification, dataset cards, acquisition specification);
- statistical-reviewer (independence and bias);
- Claude Code (descriptive CLARIFi checks, scripts, manifests).

**Skill applied:** `dataset-feasibility`.

> **What is actual and what is pending.**
> - Every count in §3 was measured on `data/raw/CLARIFi.csv` on 2026-10-21 with read-only shell tools (`grep`, `cut`, `sort`, `uniq`).
> - **No other dataset has been downloaded.** The project safety hook blocks `curl` and `wget` for Claude Code, so the DepMap, Yard, Cellosaurus, GEO and ICLAC files must be acquired by the investigator (§6).
> - The CLARIFi-to-DepMap matching counts asked for in the brief (§4 items 2–7) are therefore **pending**. They will be produced by `scripts/qc_phase_01_identifiers.py`. No anticipated values are given in their place.

---

## 1. Source verification table

| Source | Role | Version chosen | Identifier / URL | Licence | Redistribution | Verified by, date | Acquired? |
|---|---|---|---|---|---|---|---|
| **A. CLARIFi** (Oike et al. 2025) | Primary label (`clonogenic_sf`, mSF2) | Zenodo v1.0 (rev. 4) | 10.5281/zenodo.20710748; article 10.1111/cas.16334 | Dataset CC BY 4.0 vs article CC BY-NC 4.0 (**conflict**) | **Unresolved**; apply the stricter terms | Curator, auditor, 2026-10-20 | **Yes** (investigator); MD5 matches Zenodo |
| **B. DepMap Public 24Q4** | Features (`gene_expression`, basal) and identity | 24Q4 (2024-12-10) | 10.25452/figshare.plus.27993248.v1 | CC BY 4.0 (figshare record) | Allowed with attribution; kept out of Git | Curator, 2026-10-21 | **No**: `scripts/acquire_phase_01.sh` |
| B′. DepMap 23Q4 v1, Model.csv only | Identity audit (the release CLARIFi most likely used) | 23Q4 v1 | 10.25452/figshare.plus.24667905.v1, file 43346895 | CC BY 4.0 | Allowed | Curator, 2026-10-21 | **No** |
| **C. Yard et al. 2016**, Supplementary Data 1 | Secondary endpoint (`profiling_derived_survival`) | Article supplements | 10.1038/ncomms11428; PMC4848553 `ncomms11428-s2.xlsx` | CC BY 4.0 | Allowed | Curator, radiobiologist, literature-reviewer, 2026-10-21 | **No**: `--yard`; the sheet layout is unverified |
| **D. Cellosaurus** | Canonical identity (CVCL), problematic-line flags, donor and parent links | Release 56.0 (2026-06-25) | api.cellosaurus.org; archive 10.26037/yareta:lbz6rhlaavbldmavv4k5jdaphe | CC BY 4.0 (Yareta archive) | Allowed | Curator, 2026-10-21 | **No**: `scripts/fetch_cellosaurus_phase_01.py` |
| D′. ICLAC register v14 | Misidentification lookup | v14 (2026-02-15) | iclac.org xlsx | CC BY-NC-ND 4.0 | **No** (ND) | Curator, 2026-10-21 | **No**: `--optional` |
| **E. GEO GSE184119** | Context only (normal-cell, radiation-induced expression) | Supplementary files as of 2021-09-23 | GSE184119; 10.1016/j.dib.2022.107828 | GEO terms unverified; article CC BY | Unverified | Curator, radiobiologist, 2026-10-21 | **No**: `--optional` |
| **F. NCI-60** (Amundson et al. 2008; GSE7505) | Possible clonogenic SF2 for about 60 lines | — | 10.1158/0008-5472.CAN-07-2120; GSE7505 | Article paywalled | — | Curator, literature-reviewer, 2026-10-21 | **Deferred** (§5.4) |

Manifests are in `data/manifests/` (one per row). Fields that need the files themselves (SHA-256, sizes, line counts) are `null` until acquisition.

---

## 2. Dataset cards (summary)

The full cards are in the manifests.

### 2.1 CLARIFi (Dataset A)
- **Content:** 285 lines; columns `CCLE Name`, `Depmap ID`, `mSF2`.
- **mSF2:** per-line median of literature clonogenic SF2 (photon, 2 Gy), compiled from 926 studies.
- **Limits:**
  - Values per line are not in the file (graphical only, article Fig. 1C).
  - Whether the median is taken across studies or across values is not stated.
  - DepMap release unstated (portal accessed 2023-12-01).
  - Licence conflict.
  - Possible inclusion of NCI-60/Amundson or Yard-associated values among its sources (unknown).
- **Reliability evidence:** mSF2 vs single-institution SF2 r = 0.50 (n = 23) (Oike 2025).

### 2.2 DepMap 24Q4 (Dataset B)
| File | Size | Content |
|---|---|---|
| `Model.csv` | 645,696 B | ModelID, CCLEName, RRID, PatientID, OncotreeLineage, … |
| `OmicsExpressionProteinCodingGenesTPMLogp1.csv` | 506,628,654 B | log2(TPM+1), RSEM, unstranded mode |
| `OmicsProfiles.csv` | 254,733 B | Includes the `Stranded` batch variable |
| `OmicsDefaultModelProfiles.csv` | 90,080 B | Profile-to-model map |
| `README.txt` | 43,103 B | Release notes |

- MD5 checksums are published on figshare.
- Model IDs can be merged or retired between releases, and no public list of retired IDs exists, so every unmatched ID goes to a human.
- Later releases (25Q2+) are portal-only, with no DOI or published checksums that could be verified.

### 2.3 Yard et al. 2016 (Dataset C)
- 533 lines, 26 cancer types.
- CellTiter-Glo ATP readout at day 9; ¹³⁷Cs at 0.91 Gy/min; 1–10 Gy.
- Endpoint: integral survival (0–7).
- Only 15 lines (not named) were compared with clonogenic assays (r = 0.85–0.89). **No SF2.**
- Re-curated versions differ: 498 lines (RadioGx; Manem 2019) and 511 lines (Kolnohuz 2024). The version used must be named.
- CLARIFi reports mSF2 vs integral survival r = 0.28 (n = 187).

### 2.4 Cellosaurus (Dataset D)
- Batched API queries by DepMap ID instead of a full-database download.
- Verified accessions:
  - MCF-7: CVCL_0031 (ACH-000019);
  - DU145: CVCL_0105 (ACH-000979);
  - V79: CVCL_2234 (Chinese hamster; not in DepMap).
- 1,392 records carried a "Problematic cell line" comment on 2026-10-21.

### 2.5 GSE184119 (Dataset E): no-go as a label or feature source
- Six normal human primary cell types; 0 and 10 Gy (5 × 2 Gy for ADSC and LEC only); RNA at 4 h; 2 replicates; 28 samples.
- **No measured radiosensitivity.**
- No Cellosaurus or DepMap identifiers, so no join with CLARIFi.
- "HMEC" here means microvascular endothelial cells, not mammary epithelial cells.
- **Suitability for an exploratory normal-cell analysis:**
  - suitable *only* for a qualitative, pathway-level cross-reference (endpoint rule R6);
  - not for any measure of normal-cell radiosensitivity, selectivity or radioprotection;
  - its gene-expression outcomes are radiation-induced changes, not experimentally measured radiosensitivity.

### 2.6 NCI-60 (Dataset F): deferred
- Amundson et al. 2008 measured clonogenic survival (2 and 8 Gy γ) in the NCI-60 + 3 lines. GEO GSE7505 holds the expression data.
- The per-line SF2 values sit in the paywalled article (HTTP 403). Their location and assay details are **unverified**.
- **Role assessment:**
  - It is the only candidate same-endpoint (clonogenic) external set.
  - But (i) at n ≈ 60 it can only detect gross failure (95% CI width about 0.47 at r = 0.3);
  - (ii) many NCI-60 lines (e.g. MCF7, DU-145) are probably in CLARIFi;
  - (iii) CLARIFi's literature medians may already include Amundson's values, which would make "external validation" circular.
- **Recommendation:** obtain the article through institutional access, confirm the SF2 table and assay, and check whether Amundson 2008 is among CLARIFi's 926 source papers (Data S2) **before** any download.

---

## 3. CLARIFi descriptive audit (actual results, 2026-10-21)

Measured on the unchanged `data/raw/CLARIFi.csv` (MD5 `6f52f03db6d33ad9a0cac9f3dbbcbb2d`, matching Zenodo).

| Check | Result |
|---|---|
| Data rows | **285** (plus header) |
| Fields per row | 3 in all 285 rows |
| DepMap ID format `^ACH-[0-9]{6}$` | 285 / 285 |
| Duplicate DepMap IDs | 0 |
| Duplicate CCLE names | 0 |
| Blank mSF2 cells | 0 |
| Non-numeric mSF2 cells | 0 |
| Line endings | CRLF; no byte-order mark; last line has no terminator |
| CCLE names without a tissue suffix | 0 |
| Distinct CCLE tissue suffixes | **24**. The article reports 28 cancer types under a different taxonomy (unresolved) |
| MCF-7 | Present: `MCF7_BREAST`, ACH-000019 (matches the Cellosaurus DepMap cross-reference) |
| DU145 | Present: `DU145_PROSTATE`, ACH-000979 (matches the Cellosaurus DepMap cross-reference) |
| V79 | Absent (hamster line; expected) |

**Tissue distribution** (CCLE-name suffix as distributed; *not yet* reconciled with DepMap OncotreeLineage):

| Suffix | n | Suffix | n | Suffix | n |
|---|---|---|---|---|---|
| LUNG | 51 | BREAST | 17 | ENDOMETRIUM | 7 |
| CENTRAL_NERVOUS_SYSTEM | 30 | PANCREAS | 16 | STOMACH | 6 |
| LARGE_INTESTINE | 25 | URINARY_TRACT | 11 | SOFT_TISSUE | 6 |
| HAEMATOPOIETIC_AND_LYMPHOID_TISSUE | 22 | SKIN | 10 | LIVER | 6 |
| UPPER_AERODIGESTIVE_TRACT | 17 | OVARY | 10 | PROSTATE | 5 |
| OESOPHAGUS | 17 | BONE | 10 | PLEURA | 5 |
| | | | | KIDNEY | 4 |
| | | | | AUTONOMIC_GANGLIA | 4 |
| | | | | THYROID | 3 |
| | | | | SMALL_INTESTINE | 1 |
| | | | | SALIVARY_GLAND | 1 |
| | | | | BILIARY_TRACT | 1 |

- Total = 285.
- 12 suffixes have at least 10 lines; together they hold 236 lines.
- 12 suffixes have fewer than 10 lines; together they hold 49 lines.
- 3 suffixes have exactly 1 line.

**Deliberately not computed:** any summary of mSF2 values (mean, distribution, by tissue). The statistical-reviewer recommends keeping it that way until the phase_02 protocol is frozen (SR-08), because such summaries would influence choices about tissue collapsing, transformations and outliers.

---

## 4. CLARIFi ↔ DepMap feasibility counts (the brief's items 1–8)

| # | Item | Status / value |
|---|---|---|
| 1 | Total original CLARIFi cell lines | **285** (actual) |
| 2 | Lines with verified DepMap identifiers | **Pending**. All 285 carry a well-formed ACH ID; whether each exists in 24Q4 (and in 23Q4 v1) is measured by `scripts/qc_phase_01_identifiers.py` (`matched_in_model_table`, `unmatched_ids`, `ccle_name_mismatches`) |
| 3 | Lines with suitable molecular data | **Pending** (`with_default_rna_profile`, `in_expression_matrix`). The article reports CCLE mRNA for 260 lines in its NFE2L2 analysis (Oike 2025, cBioPortal). That is a different release and route, so it is reported here as context, not as our count |
| 4 | Unmatched or ambiguous lines | **Pending** (`unmatched_ids`, `ccle_name_mismatches`, `cellosaurus_unresolved`) |
| 5 | Missing required variables | Outcome: 0 blank (actual). RRID, lineage and expression: **pending** (`missing_rrid` and the item 3 fields) |
| 6 | Potentially usable complete records | **Pending** (`complete_identity_and_expression`; then minus problematic and unresolved lines after human review) |
| 7 | Tissue-type distribution | CCLE suffix: §3 (actual). DepMap OncotreeLineage for complete records: **pending** (`oncotree_lineage_counts_complete`) |
| 8 | MCF-7 and DU145 | **Present by verified identifiers** (actual): ACH-000019 = CVCL_0031 and ACH-000979 = CVCL_0105 (Cellosaurus, curator). Expression availability: **pending** (`moringa_lines` in `summary.json`) |

**Decision thresholds for these pending counts** are set out in `docs/phase_01_recommendations.md` §3.

---

## 5. Overlap and independence

### 5.1 Definitions (statistical-reviewer)

| Level | Independent? |
|---|---|
| Distinct cell line, resolved to a Cellosaurus accession and grouped with sister, derived and same-donor lines | **Yes**: the unit for splitting and resampling |
| Several SF2 values for one line within CLARIFi | No: repeated measures, already collapsed by the median |
| The same line in CLARIFi and in Yard or NCI-60 | **No.** Same genome and same expression row; only the measurement differs. **A change of assay alone is not independence** |
| Technical wells (Moringa) | No: pseudo-replicates |
| Misidentified lines | The nominal identity is false; the line may duplicate another one already in the set |
| Independent publications that compiled the same underlying values (e.g. CLARIFi medians that include Amundson's SF2) | No: the outcomes are shared |

**External validation** requires all of the following:
- (a) no shared Cellosaurus component with the training lines;
- (b) an outcome generated independently of the training labels;
- (c) a model frozen before the outcomes are opened;
- (d) the same endpoint class.

A different endpoint (Yard) is a **cross-endpoint transportability** analysis, not validation.

### 5.2 Overlap status

| Pair | Known so far | Source | To be measured |
|---|---|---|---|
| CLARIFi ∩ DepMap expression | Pending | — | `qc_phase_01_identifiers.py` |
| CLARIFi ∩ Yard | 187 lines had Yard integral survival in the CLARIFi paper (matching method not described) | Oike 2025 [FT] | Join Yard SD1 by name → ModelID → CVCL (phase_01b, after `--yard`) |
| Yard ∩ NCI-60 | Not reported anywhere; Kolnohuz 2024 trained on Yard and tested on NCI-60 without an overlap check | Literature review B8 | After the NCI-60 source is resolved |
| CLARIFi ∩ NCI-60 | Unknown; probably substantial (e.g. MCF7, DU-145) | — | After the NCI-60 source is resolved |
| CLARIFi sources ⊇ Amundson / Yard values? | Unknown | — | Data S2 (926 papers) or the authors |
| Three-way overlap | **Never published** | Literature review §C | Phase_01b |
| GSE184119 ∩ any | None possible (no shared identifiers; primary normal cells) | Curator | — |

### 5.3 Same-donor and derived lines
`Model.csv` `PatientID` (donor group) is captured by the QC script (`shared_patient_id_groups`). **Correction (2026-10-21, `docs/phase_01_static_code_review.md` D1):** the Cellosaurus `hi`/`oi` fields are parsed into `linked_accessions` but are **not yet written** to the match table or the summary. Components therefore cannot be built from the current outputs until patch P01.07 is applied. Lines in one group must stay in the same split.

### 5.4 Yard (C) and NCI-60 (F): independent samples?
- Yard lines that **are not** in CLARIFi are biologically independent of the CLARIFi training lines, but their endpoint is different. They support transportability, not validation.
- Yard lines that **are** in CLARIFi are the same biology measured twice. They support an agreement analysis (already published as a correlation) and must be excluded from any "held-out" set.
- NCI-60 lines not in CLARIFi, whose values were not compiled into CLARIFi, would be the only independent same-endpoint set. After exclusions, n may be very small.

---

## 6. Acquisition commands (investigator-run)

From the repository root:

```bash
bash scripts/acquire_phase_01.sh --yard          # DepMap 24Q4 core + 23Q4 v1 Model.csv + Yard SD1
python3 -I scripts/fetch_cellosaurus_phase_01.py # Cellosaurus r56 batches with sidecars
PYTHONPATH=src python3 scripts/qc_phase_01_identifiers.py --allow-dirty
# optional context sources:
bash scripts/acquire_phase_01.sh --optional      # GSE184119 + ICLAC v14
```

**What each step does:**
- **Downloads:**
  - never overwrite an existing file;
  - stop on any MD5 mismatch against figshare;
  - write `SHA256SUMS` in each raw folder.
- **Cellosaurus:** responses are saved unchanged, with URL, UTC access time and SHA-256.
- **QC outputs** (all gitignored; none contains mSF2 values) go to `results/tables/phase_01/identifier_qc/`:
  - `clarifi_identifier_match.csv`;
  - `summary.json`;
  - `run_record.json`.

**Run unit tests first** (synthetic fixtures; no data, no models):

```bash
conda activate explainable-radiosensitivity-ml   # configured name (O01.16); see README for the legacy moringa-rad environment
PYTHONPATH=src python3 -m pytest tests/test_safety_hooks.py tests/test_cellosaurus.py tests/test_qc_identifiers.py -q
```

**After running:**
1. Copy the SHA-256 values and sizes into the manifests.
2. Set `access_date`, `retrieved_by` and `provenance_status`.
3. Send `summary.json` to Claude Code, which will fill §4 and the OncotreeLineage table.

PMC may refuse scripted downloads of the Yard files. If so, download them in a browser and record `retrieval_method: manual`.

---

## 7. Dataset quality table

| Dataset | Endpoint class | n (lines) | Assay / timing | Dose | Replicates and uncertainty | Main quality risks | Go / no-go |
|---|---|---|---|---|---|---|---|
| CLARIFi | `clonogenic_sf` | 285 (actual) | Clonogenic, literature (1–3 weeks) | 2 Gy, photon | Values per line unknown; no per-line SE | Heterogeneous labs; median of an unknown number of values; noise (r = 0.50 vs in-house); licence | **Go** (primary label), with conditions |
| DepMap 24Q4 | `gene_expression` (basal) | Pending | RNA-seq, RSEM | — | One default profile per model | Stranded vs unstranded batch; ID drift | **Go** (features) |
| Yard 2016 | `profiling_derived_survival` | 533 (article) | ATP CellTiter-Glo, day 9 | 1–10 Gy ¹³⁷Cs | ≥ 4 wells; supplement structure unverified | Different endpoint; growth-rate confounding; version differences | **Conditional go** (secondary only) |
| Cellosaurus r56 | Identity | — | — | — | — | Free-text matching too broad; require an exact DepMap cross-reference | **Go** |
| ICLAC v14 | Identity flag | 608 entries | — | — | — | ND licence | **Go** (lookup only) |
| GSE184119 | `gene_expression` (induced) | 6 cell types, 28 samples | RNA-seq, 4 h | 10 Gy; 5 × 2 Gy | 2 per arm | No survival endpoint; no identifiers | **No-go** for labels; optional context |
| NCI-60 / Amundson | `clonogenic_sf` (if obtained) | about 60 | Clonogenic | 2 and 8 Gy γ (abstract) | Unverified | Paywalled; possible duplication with CLARIFi | **Defer** |

---

## 8. Reconciliation plan (not executed)

1. Verify checksums against the manifests; stop on any mismatch.
2. Join CLARIFi `Depmap ID` to 24Q4 `ModelID` by **exact match**. Log every unmatched ID and name mismatch. Look unmatched IDs up in 23Q4 v1 and Cellosaurus. **Never remap silently**; a human resolves each case.
3. Canonical key: the Cellosaurus `ac` whose DepMap cross-reference equals the ACH ID, and which agrees with `Model.RRID`. Flag problematic, ICLAC-listed, shared-PatientID and parent/child lines.
4. Reconcile the CCLE suffix with OncotreeLineage and with the article's 28 types. Decide the grouping vocabulary in the protocol.
5. Expression: default RNA profile only. Carry `Stranded` as a batch variable. Missing stays missing. Any gene filtering or scaling happens inside training folds (phase_03).
6. Yard: a separate `profiling_derived_survival` table, **never** merged into the mSF2 column.
7. Overlap tables on the canonical key, before any split.

## 9. Go / no-go matrix (curator; reviewed by the statistical-reviewer)

| Criterion | Status | Blocking? |
|---|---|---|
| Primary label exists, with defined endpoint and provenance | Yes (CLARIFi) | — |
| Licence permits research use | Yes, under the stricter terms | Blocks redistribution only |
| Features for most labelled lines | **Pending** | **Yes**, until the QC is run |
| Identity resolvable to a canonical key | Plan ready; pending the run | Yes, for the split design |
| Label uncertainty per line | Unavailable (needs Data S2 or the authors) | No (limitation); blocks aim C5 |
| Independent same-endpoint external set | Not available at adequate power | No (limitation); shapes the claims |
| Secondary endpoint for transportability | Yard (conditional) | No |

## 10. Checks performed and not performed

**Performed:**
- descriptive CLARIFi checks (§3);
- MD5 previously matched to Zenodo;
- byte-order-mark check;
- web verification of metadata by the curator and literature-reviewer;
- ruff check and format check on the new code.

**Not performed:**
- any download;
- the DepMap and Cellosaurus matching;
- opening the Yard supplement;
- NCI-60 data;
- running the unit tests (pytest is blocked for Claude Code by the settings `python` deny rule; the investigator runs them);
- any statistics on mSF2.
