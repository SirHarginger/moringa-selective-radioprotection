# Phase 01 endpoint compatibility assessment

**Status:** phase_01 draft for investigator review, 2026-10-21. Prepared by the **radiobiologist** subagent and written to disk by Claude Code without changes to its substance.

**Cross-review:**
- The statistical-reviewer and ml-methodologist reviewed the same endpoints independently and agree with rules R1–R10. Where they add to them, the points are listed in §9.
- The radiogenomics-curator independently checked the Yard assay against the paper's Methods (CellTiter-Glo at day 9; ¹³⁷Cs at 0.91 Gy/min; 1–10 Gy; integral survival on a 0–7 scale) and GSE184119 against its GEO record and FTP listing. Both checks agree with §2.3 and §2.7.

**Nothing in this document was computed from data.** No dataset was downloaded, no file of values was analysed and no model was run. The only local data file touched was `data/raw/CLARIFi.csv`, to test whether two DepMap identifiers are present; no `mSF2` value was read.

**Purpose.** Before any modelling target is fixed in `docs/protocol.md`, this document decides:
- which radiation-response endpoints measure the same biological quantity;
- which can be related under stated assumptions;
- which must never be pooled.

It is the evidence base for the `endpoint_class` separation already required by `docs/data_management.md` §5.

**Labels used:**
- **[V]** verified from a primary source cited here (DOI or PMID checked via Crossref, PubMed or Europe PMC, or open-access full text);
- **[NS]** not stated in the source;
- **[P]** this project's reasoning or hypothesis, not a measured result.

---

## 1. Endpoints under assessment

| # | Endpoint | `endpoint_class` | Candidate source |
|---|---|---|---|
| A | Clonogenic SF2 (single study) | `clonogenic_sf` | Individual publications; CLARIFi's underlying studies |
| B | mSF2 (per-line median of literature SF2 values) | `clonogenic_sf` (derived) | CLARIFi v1.0 (`data/manifests/clarifi__v1_0.yaml`) |
| C | ATP-based radiation-response profiling | `profiling_derived_survival` | Yard et al. 2016 |
| D | Dose–response integrals (integral survival, AUC, mean inactivation dose) | `profiling_derived_survival` or `model_derived` | Yard et al. 2016; Guerra Liberal & McMahon 2023 |
| E | Crystal-violet proliferation (optical density, OD) | `proliferation_crystal_violet` | Moringa manuscript; general literature |
| F | Moringa proliferation enhancement factor (PEF = *A*₂Gy / *A*₀Gy) | `proliferation_optical_density` (derived interaction ratio) | Moringa manuscript (motivation only) |
| G | Radiation-induced gene expression | `gene_expression` | GEO GSE184119 |

---

## 2. Endpoint-by-endpoint assessment

### 2.1 A: Clonogenic SF2 (single study)

- **Biological quantity.** The fraction of irradiated cells that keep unlimited proliferative capacity (reproductive integrity) after 2 Gy. It is a survival endpoint, not a growth-rate endpoint.
- **Assay principle [V].**
  - Cells are seeded at low density, irradiated, grown into colonies, fixed, stained and counted; a colony is conventionally ≥ 50 cells.
  - Surviving fraction = colonies ÷ cells seeded, corrected for the plating efficiency of the unirradiated control.
  - Sources: Franken et al. 2006, *Nat Protoc* 1:2315–2319, DOI 10.1038/nprot.2006.339; Guerra Liberal & McMahon 2023, *Int J Mol Sci* 24:7861, DOI 10.3390/ijms24097861, PMID 37175568.
- **Timing [V].** About 1–3 weeks of colony growth (7–11 days in Guerra Liberal & McMahon). The assay spans many divisions, so it scores reproductive death rather than short-term metabolic state.
- **Radiation conditions [V, example].** Guerra Liberal & McMahon used 0–8 Gy X-rays at 225 kVp, 13.3 mA, 0.59 Gy/min. Conditions vary widely across the literature; record them per study and never assume them.
- **Controls and normalisation [V].** The dose-0 plating efficiency of the same line in the same experiment: a within-experiment, untreated normaliser. This is a structural difference from endpoint F (§2.6).
- **Replicate structure [V, example].** Guerra Liberal & McMahon: triplicate experiments, mean ± SD, linear-quadratic fit by weighted non-linear regression.
- **Reproducibility [V].**
  - Nuryadi et al. 2018, *Oncotarget* 9:13706–13712 (DOI 10.18632/oncotarget.24448, PMID 29568388, PMC5862609). Cell line A549. In both 20 independent in-house experiments and 192 publications, the coefficient of variation (CV) of SF2 and D₁₀ was **below 30%**. In the published data, the timing of cell seeding significantly affected SF2.
  - Matsui et al. 2019, *Int J Mol Sci* 20:4148 (DOI 10.3390/ijms20174148, PMID 31450688, PMC6747107). 620 experiments on the eight most frequently assayed lines. CV of SF2 and D₁₀ was below 30% for every line; the authors conclude that pooled analysis of published clonogenic data is defensible.
  - Counterweight: Guerra Liberal & McMahon describe "very large variation" in published survival values for several common lines. **Transcription caveat:** line names in the fetched full text rendered ambiguously (e.g. "HT116", "HT1299"); re-read the figure before citing.
  - [P] These two observations do not conflict. A CV near 0.3 on a quantity bounded in [0, 1] is large relative to the between-line spread we intend to model. Measurement noise is therefore a first-order limit on achievable model performance, not a reason to reject the endpoint.
- **Comparable with:** B (A is B's input) and other clonogenic SF2 values measured under recorded conditions.
- **Not comparable with:** E or F. Only weakly relatable to C and D (§3.2).

### 2.2 B: mSF2 (CLARIFi)

- **Biological quantity.** A literature-consensus estimate of the same quantity as A: the per-cell-line **median** of published SF2 values from photon irradiation measured by clonogenic assay.
- **Construction [V]** (Oike et al. 2025, *Cancer Sci* 116:690–697, DOI 10.1111/cas.16334, PMID 39668120, PMC11875790; dataset DOI 10.5281/zenodo.20710748):
  - PubMed searches on 2018-12-30 combined 1,048 CCLE line names with X-rays, gamma rays or radiation.
  - A deep-learning screen plus manual review of 33,284 papers gave 926 relevant studies.
  - Result: SF2 for **285 cell lines across 28 cancer types**.
  - Inclusion: English-language, photon, clonogenic.
  - **Exclusion:** concomitant reagents, plasmids or siRNAs given with radiation. Solvent, scrambled-siRNA and empty-vector controls were accepted.
  - Values were taken from the text or read off survival curves, recorded to two decimal places.
- **Why a median [V].** Chosen over the mean because some lines have few contributing values.
- **Replicate structure [NS].** Neither the number of values per line nor whether the median is across studies or across individual measurements is stated. [P] mSF2 therefore carries **no per-line uncertainty**, and precision weighting is impossible without re-extracting the primary values.
- **Internal consistency [V].**
  - mSF2 vs in-house SF2: r = 0.50, p = 0.014 (n = 23). For lines with ≥ 3 papers: r = 0.60, p = 0.0063 (n = 19).
  - The authors report that none of the experimental parameters they examined (seeding timing, radiation type, dose rate) significantly affected the endpoints. This partly conflicts with Nuryadi et al.'s seeding-timing finding; record it as a covariate, not a settled question.
- **Radiation conditions.** Photon and 2 Gy by construction [V]. Source, energy and dose rate vary per study and are **not in the released table** [NS].
- **Identifiers [V].** `CCLE Name` and `Depmap ID`. The reference list says "Accessed December 1, 2023"; the DepMap release itself is [NS].
- **Publication structure [V].** 492 of 926 papers (53.1%) report a single cell line.
- **Comparable with:** A (same quantity, aggregated).
- **Not comparable with:** E or F. Relatable to C and D only as a weakly correlated endpoint that ranks cancer types differently (§2.3).
- **Caution [P].** CLARIFi excludes concomitant-reagent studies, so mSF2 is an **untreated-baseline** endpoint by design. Any modifier-treated measurement, including the whole Moringa experiment, falls outside its definition.

### 2.3 C: ATP-based radiation-response profiling (Yard et al. 2016)

Yard BD, Adams DJ, Chie EK, et al. *Nat Commun* 2016;7:11428. DOI 10.1038/ncomms11428, PMID 27109210, PMC4848553. Verified from the open-access full text.

- **Assay [V].** Luminescent ATP quantification with **CellTiter-Glo** (50% solution in PBS) in white 384-well plates.
- **Timing [V].** Read **9 days after irradiation**.
- **Doses and radiation [V].** 1, 2, 3, 4, 5, 6, 8 and 10 Gy from a **¹³⁷Cs** source (GammaCell 40 Exactor) at **0.91 Gy/min**.
- **Scale [V].** 533 human tumour cell lines from 26 cancer types.
- **Seeding and replicates [V].** Three densities of 25–225 cells per well; per line, a density within the linear range of the luminescence signal was chosen; at least quadruplicate wells.
- **Summary metric [V].** "Integral survival":
  - trapezoidal integration over log₂-transformed dose;
  - rescaled by 7 / log₂(10), so values run from 0 (fully sensitive) to 7 (fully resistant);
  - how the per-dose values were normalised before integration is [NS].
- **Clonogenic validation [V].** Platform vs clonogenic integral survival in 15 lines: r = 0.85 (single experiment) and r = 0.89 (mean of two). **No SF2 values are reported.**
- **What it measures [P].** The ATP content of the remaining adherent population 9 days after irradiation. That depends jointly on clonogenic survival, the growth rate of the survivors, division delay and per-cell metabolism. It is a **growth-and-survival composite**, not a surviving fraction.
- **ATP readouts configured for SF2 [V].** Tam et al. 2005, *Gynecol Oncol* 96:765–770 (DOI 10.1016/j.ygyno.2004.11.025, PMID 15721424): in five cervical lines, SF2 by ATP assay was 0.28–0.67 vs 0.27–0.70 by clonogenic assay. [P] This supports only the narrow claim that an ATP assay set up to estimate SF2 can track it in a small panel. It does not make Yard's 9-day integral survival a surrogate for SF2.
- **Decisive constraint [V].**
  - Oike et al.: mSF2 vs Yard integral survival r = 0.28, p < 0.001 (n = 187). For lines with ≥ 3 papers: r = 0.35 (n = 84).
  - The two endpoints rank cancer types differently: breast and liver rank high for integral survival but low for mSF2.
  - [P] r ≈ 0.3 is about 10% shared variance. These are related but distinct endpoints and must never share a target column.

### 2.4 D: Dose–response integrals (integral survival, AUC, mean inactivation dose)

- **Biological quantity.** A whole-curve summary, dominated by the intermediate-to-high-dose region rather than by the initial slope that SF2 reports.
- **Mean inactivation dose (MID) [V].** The area under the LQ-fitted survival curve, in Gy. Guerra Liberal & McMahon report:
  - MID 1.3–3.4 Gy across 27 normal, lung-cancer and prostate-cancer lines, falling to 0.65 Gy in Lig4⁻/⁻ cells;
  - SF2 ranging from 0.041 to 0.71.
- **Yard integral survival [V].** Dimensionless, 0–7, on a log₂ dose axis. **Not the same quantity as MID**, and the two cannot be converted without the per-dose survival values and a stated normalisation.
- **Timing and radiation.** Inherited from the generating assay.
- **Model dependence [P].** MID also depends on the fitted model and on the integrated dose range, so two MIDs from different dose ranges are not comparable.
- **Rule [P].** Every integral endpoint must record five things: (i) the generating assay, (ii) the dose range, (iii) the dose-axis transformation, (iv) the normalisation and (v) the unit. Without all five it is `unknown` and is not used for modelling.

### 2.5 E: Crystal-violet proliferation (OD)

- **Biological quantity.** Adherent biomass at one fixed time point.
- **Assay principle [V].** Crystal violet stains attached cells; detached cells are washed away (Feoktistova, Geserick & Leverkus 2016, *Cold Spring Harb Protoc* pdb.prot087379, DOI 10.1101/pdb.prot087379).
- **Timing.** 72 h in the Moringa study.
- **What it cannot do [P].**
  - It cannot separate cell number from dye uptake per cell, or survival from proliferation rate.
  - It cannot detect reproductive death: a lethally damaged cell that stays attached still contributes OD.
  - Division delay and cell enlargement push OD in opposite directions.
- **Terminology trap [V/P].** Crystal violet is also the standard colony stain in clonogenic assays. It is the same dye but a different endpoint, so pipelines must key on endpoint definitions, never on stain names.
- **Comparable with:** only the same protocol, time point, normalisation and cell line.

### 2.6 F: Moringa proliferation enhancement factor (PEF)

- **Definition [V, manuscript].** *A*_D is the area under ΔOD (relative to the dose-matched untreated control) plotted against extract concentration. PEF = *A*₂Gy / *A*₀Gy (`docs/moringa_scientific_linkage.md` §6).
- **Biological quantity.** An extract × dose interaction measure on 72-h adherent biomass.
- **It is not a survival quantity [P].** Each *A*_D is referenced to its own dose-matched control, so PEF contains no untreated radiation response. PEF > 1 does not mean growth above the untreated control, and the ratio becomes unstable if *A*₀Gy approaches zero or changes sign.
- **Radiation [V].** A single 2 Gy dose from a Precision MultiRad 160 at 1 Gy/min. kVp, filtration and dosimetry are [NS].
- **Replicates [V].**
  - Three wells per sample.
  - Two 24-well plates per cell line per extract, one plate per dose, so **dose is confounded with plate**.
  - No independent biological repeats are described.
- **Unresolved inconsistencies [V].**
  - Tabulated *A*_D values are all positive, while the plotted ΔOD is mostly negative for DU145 and MCF-7.
  - *A*_D is printed with the unit "µg/ml".
  - The integration method and the sign convention are [NS].
  - Concentration units are inconsistent (mg/ml vs µg/ml).
- **Comparable with:** nothing in this project.
- **Rule [P].** PEF is never a modelling target or validation target, is never put on an axis with a survival endpoint, and is never described as radioresistance, radiosensitivity or radioprotection.

### 2.7 G: Radiation-induced gene expression (GSE184119)

Shukla L, Lee SA, Du MRM, Karnezis T, Ritchie ME, Shayan R. A transcriptomic dataset evaluating the effect of radiotherapy injury on cells of skin and soft tissue. *Data in Brief* 2022;41:107828. DOI 10.1016/j.dib.2022.107828, PMID 35127999, PMC8803966. A correction was published as DOI 10.1016/j.dib.2022.108358; its content has not been read.

- **What it is [V].** RNA-seq of **normal human** skin and soft-tissue cells: dermal fibroblasts (NHDF), keratinocytes (NHEK), placental pericytes (PERI), microvascular endothelial cells (HMEC; **not** mammary epithelial cells), lymphatic endothelial cells (LEC) and adipose-derived stem cells (ADSC).
- **Radiation [V].**
  - Every cell type: a single 10 Gy dose vs 0 Gy.
  - ADSC and LEC only: an additional arm of 5 × 2 Gy over 48 h.
  - Gammacell 40 irradiator; dose rate not stated.
- **Timing [V].** RNA collected 4 h after irradiation.
- **Replicates [V].** Two biological replicates per arm; 28 samples. The source is ambiguous: it also mentions "duplicate or triplicate".
- **Platform [V].** Illumina HiSeq 4000 (GPL20301).
- **Reported content [V].**
  - 243 differentially expressed genes (DEGs) for 10 Gy vs 0 Gy.
  - 70 DEGs for fractionated vs 0 Gy.
  - No DEGs between fractionated and single dose.
  - Consistently altered genes include ATF3, SELE, CDKN1A, GDF15 and MDM2, with p53-pathway enrichment.
- **No measured radiosensitivity.** GSE184119 has no survival data, no cancer lines and no DepMap or Cellosaurus identifiers, so it has no identifier overlap with CLARIFi (curator: verified against the GEO record).
- **Legitimate uses [P]:** a qualitative, pathway-level cross-reference, and an example of a normal-tissue resource.
- **Illegitimate uses [P]:**
  - as a training target;
  - as features joined to CLARIFi;
  - as evidence of selectivity or radioprotection.
- **Features vs outcomes [P].** Baseline expression is a feature. Radiation-induced change is an outcome or mechanism, and using it as a feature would introduce a post-treatment variable.

---

## 3. Cross-cutting axes

### 3.1 Dose
Only A, B and F involve 2 Gy. C and D span 1–10 Gy, and G uses 10 Gy or 5 × 2 Gy.

[P] The coincidence that the Moringa experiment used 2 Gy, the same dose as SF2, is the most tempting false bridge in this project. The protocol must state it explicitly: **the same dose does not make endpoints comparable.**

### 3.2 SF2 specifically
- SF2 describes the initial-slope region of the survival curve; integrals describe its shape.
- Two pieces of evidence show that these are not substitutable even within the survival family: mSF2 and Yard integral survival correlate at only r ≈ 0.28–0.35, and they rank cancer types differently.

### 3.3 Assay duration
| Assay | Duration | What it scores |
|---|---|---|
| Clonogenic | ~7–21 days | Colony formation |
| ATP profiling | 9 days | ATP content |
| Crystal violet | 72 h | Adherent biomass |
| Gene expression | 4 h | Transcript abundance |

[P] Duration largely sets how much proliferation contributes to the signal:
- 4 h: minimal.
- 72 h to 9 days (biomass and ATP): maximal, and a confounder.
- Clonogenic assays: proliferation over many generations is what is being scored, so it is part of the definition, not a confounder.

### 3.4 Radiation quality
| Source | Radiation | Dose rate |
|---|---|---|
| CLARIFi | Photons by inclusion; energy not in the table [NS] | Not in the table |
| Yard | ¹³⁷Cs γ [V] | 0.91 Gy/min [V] |
| Guerra Liberal & McMahon | 225 kVp X-rays [V] | 0.59 Gy/min [V] |
| Moringa | 160-kVp-class X-ray [V]; kVp and filtration [NS] | 1 Gy/min [V] |
| GSE184119 | Gammacell 40; isotope [NS] | [NS] |

Evidence on whether photon quality matters is mixed:
- McElligott et al. 2024, *Med Phys* 51:3796–3805 (DOI 10.1002/mp.17060, PMID 38588477), estimate by simulation an RBE of 1.14 for DSB induction by kV beams, citing a literature range of 1.03–1.82. The reference radiation must be confirmed from the full text before this is cited.
- Matsui 2019 and Oike 2025 found no significant effect of radiation type or dose rate in pooled clonogenic data.

[P] Record photon quality and dose rate as covariates and pre-specify a sensitivity analysis.

### 3.5 Proliferation versus survival
This is the central confounder.
- Clonogenic survival is the only endpoint here defined by reproductive integrity.
- ATP at 9 days and crystal violet at 72 h both scale with the growth rate of the survivors.
- [V] Guerra Liberal & McMahon found that across their panel, **only plating efficiency and the percentage of cells in S phase** were significantly associated with radiosensitivity.
- [P] Proliferation-related features are therefore both plausible biology and plausible assay artefact. A proliferation-only baseline is needed.

### 3.6 DNA repair
- [V] In CRISPR-engineered repair-deficient lines, residual DSBs predicted survival well (R² = 0.78 against an independent CRISPR screen; BRCA1 was the exception).
- [V] In unmodified normal and cancer lines, repair parameters did **not** correlate strongly with radiosensitivity.
- [V] GSE184119 shows an acute p53-pathway response at 4 h after 10 Gy.
- [P] DNA repair is therefore a mechanistic covariate, not an interchangeable endpoint. Repair-gene attributions do not establish a repair mechanism.

### 3.7 Normal tissue versus tumour selectivity
- CLARIFi contains cancer lines only [V].
- Guerra Liberal & McMahon include normal lines assayed under one protocol [V].
- GSE184119 is normal tissue only and transcriptomic [V].
- [P] A selectivity claim needs normal and tumour measurements on the same endpoint, under the same conditions, with the same treatment status. CLARIFi combined with GSE184119 cannot meet that standard.

### 3.8 Confounding to control or record
No mechanisms are proposed here.
1. **Publication origin.** 53.1% of the CLARIFi papers report a single line, so line identity is partly confounded with laboratory and publication.
2. **Measurement-noise ceiling.** SF2 CV < 30% sets an upper bound on achievable performance.
3. **Seeding and plating.** These are at once biology, an assay parameter and a candidate feature.
4. **Growth rate** (endpoints C, D, E, F); see §3.5.
5. **Batch and plate** (F). Dose is confounded with plate.
6. **Treated vs baseline estimand.** F is treated; A and B are untreated baselines.
7. **Species, tissue and malignancy** (F). In the Moringa design these are mutually confounded.
8. **Definition drift within a class.** "Crystal violet" and "AUC" each name more than one quantity.
9. **Dose-axis transformation.** Must travel with any integral value.
10. **RBE.** Never quote one without its reference radiation.

---

## 4. Pairwise compatibility matrix

Legend:
- **✓** compatible: may be combined within one `endpoint_class`, with covariates recorded.
- **~** relatable only under the assumptions below, as separate columns reported side by side; never averaged into one target.
- **✗** not compatible: never combined, substituted or co-plotted on a shared value axis.

|  | A SF2 | B mSF2 | C ATP | D integrals | E CV-OD | F PEF | G induced GEx |
|---|---|---|---|---|---|---|---|
| **A SF2** | ✓ | ✓ | ~ | ~ | ✗ | ✗ | ✗ |
| **B mSF2** | ✓ | ✓ | ~ | ~ | ✗ | ✗ | ✗ |
| **C ATP** | ~ | ~ | ✓ | ~ | ✗ | ✗ | ✗ |
| **D integrals** | ~ | ~ | ~ | ~ (identical derivation only) | ✗ | ✗ | ✗ |
| **E CV-OD** | ✗ | ✗ | ✗ | ✗ | ✓ (identical protocol) | ✗ | ✗ |
| **F PEF** | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ (none exists) | ✗ |
| **G induced GEx** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ (same dose, time, platform) |

Assumptions behind each "~":
- **A/B ↔ C.** Assumes a monotone relation between survival and 9-day ATP. Agreement is r = 0.85–0.89 in 15 lines but r = 0.28 across 187 lines, with reversed cancer-type rankings.
  - Permitted: a cross-endpoint analysis that reports the heterogeneity.
  - Barred: pooling, imputation, or composite targets.
- **A/B ↔ D.** Partly contradicted by the ranking reversal. Use only as a separate, pre-specified secondary target.
- **C ↔ D.** Compatible within Yard's own measurement chain. Across sources, requires an identical derivation.
- **D ↔ D.** Compatible only when assay, dose range, axis transformation, normalisation and unit are all identical. MID (Gy) and Yard integral survival (0–7) cannot be interconverted.
- **E ↔ E.** OD is not a transferable scale across laboratories.

"✗" for G means "never combined as a value". Qualitative pathway cross-reference is governed by rule R6.

---

## 5. Explicit rules

**R1. Primary modelling target.** CLARIFi v1.0 mSF2, a continuous per-line endpoint keyed on a canonical cell-line identifier.
- Conditions: the licence must be resolved before any redistribution; splits are made by cell-line group; no per-line weighting is used, because per-line uncertainty is unavailable.

**R2. Secondary targets, each modelled separately.**
- (a) Individual-study clonogenic SF2, if a provenance-tracked re-extraction is ever made.
- (b) Clonogenic-derived MID, if assembled with the five fields of §2.4.
- No composite target is permitted.

**R3. External or secondary evaluation only.** Yard integral survival.
- It answers whether performance transfers across endpoint definitions.
- It is reported as **heterogeneity between endpoints**: never pooled or averaged, and never used to impute mSF2.
- The published r ≈ 0.28–0.35 is quoted every time this comparison is reported.

**R4. Never a target, never a validator.** Crystal-violet OD and PEF. PEF may never share a value axis with a survival endpoint.

**R5. Never combined under any transformation.** Every "✗" pair in §4.

**R6. Qualitative-only use of GSE184119.**
- A pathway-level cross-reference is allowed, stating its dose, time point, cell types, n and lack of identifier overlap in the same sentence.
- No cell-line-level join, no use as features or target, and no claim of selectivity or radioprotection.

**R7. Baseline vs induced features.** Only baseline (unirradiated) molecular measurements may be features.

**R8. Mandatory metadata for every endpoint row:**
- `endpoint_class`;
- assay;
- dose (Gy);
- dose-axis transformation;
- radiation type, energy or isotope;
- dose rate;
- time point;
- normaliser;
- treatment status;
- replicate type;
- source DOI or accession and release.

A row missing the assay, dose, time point or treatment status is `unknown` and excluded.

**R9. Noise ceiling and baselines.** The protocol pre-specifies:
- (i) a statement of the noise ceiling;
- (ii) a proliferation-only baseline;
- (iii) tissue-only baselines and leave-one-tissue-out evaluation.

**R10. Selectivity language.** No claim of normal-vs-tumour selectivity may be made from cancer-cell-line survival data alone.

---

## 6. Open items

1. The CLARIFi licence conflict.
2. Papers per line are not in the released table. Whether they can be recovered from Data S1/S2 is unchecked.
3. Yard's per-dose normalisation is [NS], and its supplementary files have not been retrieved (download commands are in `docs/phase_01_dataset_feasibility.md`).
4. Re-read the cell-line list in Figure 1 of Guerra Liberal & McMahon.
5. Confirm the reference radiation in McElligott et al.
6. DepMap expression coverage for the CLARIFi lines (`docs/phase_01_dataset_feasibility.md`).

## 7. Checks performed and not performed

**Performed:**
- citation verification (2026-10-21);
- extraction of assay details from the cited sources;
- a presence-only identifier check in `data/raw/CLARIFi.csv`.

**Not performed:**
- downloads;
- reading or analysis of any endpoint value;
- model runs;
- retrieval of supplementary files;
- a systematic search.

## 8. Sources verified

| Source | Identifiers | Used for |
|---|---|---|
| Oike T, et al. *Cancer Sci* 2025;116(3):690–697 | DOI 10.1111/cas.16334; PMID 39668120; PMC11875790; data DOI 10.5281/zenodo.20710748 | mSF2 construction; correlations; ranking reversal |
| Yard BD, et al. *Nat Commun* 2016;7:11428 | DOI 10.1038/ncomms11428; PMID 27109210; PMC4848553 | Assay, doses, timing, integral survival, clonogenic validation |
| Franken NAP, et al. *Nat Protoc* 2006;1(5):2315–2319 | DOI 10.1038/nprot.2006.339 | Clonogenic assay principle |
| Guerra Liberal FDC, McMahon SJ. *Int J Mol Sci* 2023;24(9):7861 | DOI 10.3390/ijms24097861; PMID 37175568; PMC10178060 | Protocol details, MID, PE and %S associations, DSB findings |
| Nuryadi E, et al. *Oncotarget* 2018;9(17):13706–13712 | DOI 10.18632/oncotarget.24448; PMID 29568388 | SF2 CV < 30%; seeding-timing effect |
| Matsui T, et al. *Int J Mol Sci* 2019;20(17):4148 | DOI 10.3390/ijms20174148; PMID 31450688 | SF2 CV < 30% (620 experiments) |
| Tam KF, et al. *Gynecol Oncol* 2005;96(3):765–770 | DOI 10.1016/j.ygyno.2004.11.025; PMID 15721424 | ATP-assay SF2 vs clonogenic SF2 |
| Feoktistova M, et al. *Cold Spring Harb Protoc* 2016 | DOI 10.1101/pdb.prot087379 | Crystal-violet principle |
| Shukla L, et al. *Data Brief* 2022;41:107828 | DOI 10.1016/j.dib.2022.107828; PMID 35127999; PMC8803966 | GSE184119 |
| McElligott O, et al. *Med Phys* 2024;51(5):3796–3805 | DOI 10.1002/mp.17060; PMID 38588477 | kV RBE |
| Stone HB, et al. *Transl Oncol* 2016;9(1):46–56 | DOI 10.1016/j.tranon.2016.01.002; PMID 26947881 | Reporting standards for drug–radiation studies |

## 9. Additional points from the statistical-reviewer and ml-methodologist

- **Haematopoietic lines (n = 22).** These often use different clonogenic formats (soft agar or suspension), and blood vs solid status alone separates mSF2 strongly (Oike 2025).
  - Recommendation: pre-specify either primary exclusion with a sensitivity analysis that includes them, or a blood/solid baseline.
  - The radiobiologist did not object. This is for the investigator to decide (O01.04).
- **Transformation.** mSF2 is bounded in [0, 1]. Decide before seeing any values whether to model it untransformed or on the logit scale.
- **No outcome summaries before the protocol is frozen.** Do not produce means or distributions of mSF2, including by tissue (statistical-reviewer SR-08).
