---
title: "From *Moringa oleifera* Radiobiology to Explainable Machine Learning: Cellular Radiosensitivity Prediction and Evidence-Based Compound Prioritisation"
subtitle: "Scientific project report"
# Optional author block, shown on the cover of every edition, e.g.
# author:
#   - "Principal investigator: <name>"
#   - "Institution: <name>"
date: "2026-10-22"
lang: en-GB
papersize: a4
geometry: "margin=25mm"
fontsize: 11pt
linestretch: 1.15
numbersections: true
toc: true
toc-depth: 2
colorlinks: true
linkcolor: "black"
urlcolor: "blue"
bibliography: references.bib
link-citations: true
# Reference style: build.sh passes --csl reports/french_embassy/apa.csl when that file is
# present (APA 7). It is not bundled; see build.sh for the one-line download.
---

<!--
This file is the authoritative source of the report. No investigator name, funding
programme, reference number, partnership or approval status has been invented; add an
author block in the YAML header above if names are to appear on the cover.

Builds: latex/build.sh (typeset PDF) and build.sh (DOCX). Figure files and numbers
resolve through figure_manifest.csv; tables through table_manifest.csv.
-->

\newpage

# Executive summary {.unnumbered}

**Research motivation.** An unpublished experimental study found that crude
dichloromethane (DCM) seed and leaf extracts of *Moringa oleifera* (Lam.) changed how
irradiated cells proliferate, and that the change differed between an apparently normal
rodent fibroblast line (V79) and two human carcinoma lines (DU145, MCF-7). That
observation raises a broader question the three-line experiment cannot answer: do cells
differ in their *intrinsic* radiation response, and can measurable molecular features
explain those differences?

**Computational research question.** Does baseline gene expression, summarised as 50
Hallmark pathway scores, predict experimentally measured clonogenic radiosensitivity
across cancer cell lines better than prespecified simple baselines, once related cell
lines are kept together and tissue of origin is already accounted for?

**Data and methods.** We assembled 241 eligible cell-line records (237 independent
biological components) by linking literature-derived clonogenic surviving fractions at
2 Gy (CLARIFi) to baseline expression (DepMap 24Q4), with identity and relatedness
resolved through Cellosaurus and pathway features from MSigDB Hallmark gene sets. Five
prespecified models, from a global mean to tissue plus proliferation plus expression, were
compared under ten repeats of five-fold cross-validation, grouped by biological component
and stratified by tissue, with all tuning and feature scaling inside training folds.
Two hundred and fifty of 250 model-fold tasks completed.

**Principal measured findings.** Adding expression features to a tissue-only baseline
reduced the mean absolute error (MAE) by **0.00383 mSF2 units, 2.85% of the baseline
MAE**, and the richer model had the lower error in **nine of ten** cross-validation
repeats. Out-of-sample R² remained near zero for every model (−0.018 to +0.013). The
honest reading is that **expression carries a small amount of usable signal beyond tissue
of origin, and that the overall predictive power is weak**. Superiority was not formally
assessed: a protocol deviation, recorded before any result was seen, deferred the coverage
simulation needed to validate an interval method, and no negative-control draws were run.
The improvement is therefore reported as a descriptive estimate, not a demonstrated
effect.

**Robustness.** Three further analyses of the same frozen cohort tested how durable that
small advantage is. A random forest (M3) did **worse** than the linear offset model
(ΔMAE 0.00275 against 0.00383). The advantage nearly vanished on the neglog outcome scale
(ΔMAE 0.00023) and was larger on the logit scale (0.00980), so its size depends on how the
outcome is expressed. Holding out one tissue at a time, an expression-only model reached
out-of-sample R² **+0.031** against a global mean — the only clearly positive R² in the
project — but it lost to the global mean in two of the nine well-supported tissues,
Pancreas (ΔMAE −0.0142) and Esophagus/Stomach (−0.0030), so transfer to an unseen tissue
is conditional. The negative controls are the one robustness analysis not executed, and
without them no pathway can exceed the exploratory tier.

**Pathway and compound prioritisation.** Held-out permutation importance ranked the 50
Hallmark scores; seven reached the prespecified exploratory tier C, led by the p53 pathway,
and tiers A and B were unreachable by design because no prediction gain was formally shown
and no negative controls exist. Separately, we curated *M. oleifera* seed and leaf
constituents from primary analytical studies and linked them to radiation-response biology
through a transparent four-dimension, 0–8 point score fixed before computation. The
curation produced one finding that shapes the whole project: **niazimicin is the only
constituent with a structurally confirmed identification in a dichloromethane fraction of
both seed and leaf, and it has no published study of the purified compound in any
radiation-response process; conversely, the compounds with the strongest radiation evidence
have never been verified in a dichloromethane extract.** Applying the score ranked **18
compounds, 5 of them in tier A**. Two prespecified safeguards visibly bound: chlorogenic
acid scored 7 of 8 yet is held at tier C because one study reports it protecting *tumour*
cells from radiation, and benzyl isothiocyanate is excluded entirely despite strong
radiation evidence because it is a root constituent, not a seed or leaf one. A tier records
the state of the evidence, never a demonstrated radioprotective effect.

**Main challenges.** An incomplete source manuscript (printed pages 3 and 7–12 are
missing); endpoints that must not be equated (crystal-violet proliferation under extract
treatment is not clonogenic SF2); cell-line identity and relatedness; a small, tissue-
imbalanced sample; a computational cost that forced the coverage simulation to be
deferred; and a chemical-composition gap, because the original extracts were never
analysed.

**Significance.** The project delivers a reproducible, auditable research pipeline and an
honest negative-leaning benchmark that agrees with the strongest prior work in the field,
together with a traceable, explicitly exploratory route from the original radiobiology to
a shortlist of compounds and a feasible validation strategy. Its value lies in the
rigour of its methods and the transparency of its evidence, not in a strong performance
claim.

**Practical next steps.** Analytically characterise the original DCM extracts; confirm the
identity of shortlisted compounds; run the deferred coverage simulation and negative
controls; and test purified compounds against whole extracts in clonogenic assays using
matched normal and tumour cells over a dose range.

\newpage

# Introduction and scientific background

## Radiation-induced cellular responses

Ionising radiation kills cells mainly by damaging DNA, and the DNA double-strand break is
the lesion most closely tied to loss of reproductive capacity. The standard measure of how
much radiation a cell population survives is the **clonogenic assay**: the fraction of
cells that retain unlimited proliferative capacity and form colonies after irradiation,
normalised to the plating efficiency of unirradiated controls [@puck1956]. The surviving
fraction at 2 Gy (SF2) is widely used because 2 Gy is the conventional daily fraction in
radiotherapy, and because SF2 correlates with clinical outcome in some settings
[@fertil1981; @west1993].

Cell lines differ substantially and reproducibly in intrinsic radiosensitivity, and those
differences are only partly explained by tissue of origin [@yard2016]. Determinants
include DNA damage response and repair capacity, cell-cycle checkpoint control,
proliferation rate, apoptotic propensity, oxygenation and redox state. Each of these
processes has a transcriptional footprint, which is what makes expression-based prediction
plausible in principle.

## The Moringa experimental motivation

The motivating study is an unpublished manuscript, *Dichloromethane seed and leaf extracts
of Moringa oleifera (Lam) enhance proliferation in irradiated rodent fibroblasts in
vitro*. The scanned copy available to this project is incomplete: printed pages 1, 2, 4, 5,
6, 13, 14 and 15 are present, and printed page 3 and pages 7–12 are missing, so the plant
material and extraction methods, the end of the discussion, the conclusions and the
reference list cannot be read. Authors, venue, date and DOI are not shown on the supplied
pages, and no published version was located. **No missing method, result or conclusion has
been reconstructed.** The full page-by-page extraction is recorded in
`docs/moringa_scientific_linkage.md`.

What the available pages do document is the following. Crude DCM seed and leaf extracts,
reconstituted in phosphate-buffered saline and sterile-filtered, were applied at 0 to
100 µg/mL to V79 (described as apparently normal Chinese hamster lung fibroblasts), DU145
(human prostate cancer) and MCF-7 (human mammary adenocarcinoma). One plate per cell line
per extract was left unirradiated and a second was irradiated to 2 Gy of X-rays at
1 Gy/min. Adherent biomass was measured 72 hours later by crystal-violet optical density
at 590 nm, with dose-matched untreated controls subtracted. The authors integrated the
change in optical density against concentration and reported a proliferation enhancement
factor, PEF = *A*~2\ Gy~/*A*~0\ Gy~. For the seed extract, PEF exceeded 1 in all three lines
(V79 1.25, DU145 1.12, MCF-7 1.16). For the leaf extract, PEF was 1.26 in V79, 0.90 in
DU145 and 0.99 in MCF-7.

Four cautions follow directly, and they constrain everything in this report:

1. **PEF is not SF2.** PEF is a ratio of integrated extract-versus-control differences in
   72-hour biomass, measured with the extract present. SF2 is a surviving fraction measured
   in untreated cells over one to three weeks of colony growth. The two must never be
   equated, pooled, or plotted on one axis.
2. **"Enhancement" is used for two different quantities in the manuscript.** By PEF, the
   seed extract enhanced all three lines; by growth relative to untreated control, only V79
   increased, while the two carcinoma lines showed no change or reduced growth. The
   discussion's statement about the apparently normal fibroblasts refers to the second
   quantity and the results' statement about all cell lines refers to the first.
3. **The normal-versus-malignant comparison is confounded.** The only apparently normal
   line is also the only non-human line, so species, tissue of origin, phenotype and
   malignancy vary together. Only the leaf extract shows any normal/malignant difference in
   PEF terms.
4. **The design does not support a selectivity claim.** There is one non-zero dose, no
   dose–response, technical wells rather than independent biological repeats, dose
   confounded with plate, and no vehicle or cell-free interference control described. The
   available pages contain no clonogenic, cytotoxicity, apoptosis, DNA-damage or migration
   assay, no normal human cell line and no mechanistic experiment.

Accordingly, this project treats the Moringa measurements as **biological motivation
only**. They are never used as training, calibration or validation data, and no claim of
selective phytochemical radioprotection is made anywhere in this report.

## Why predicting cellular radiosensitivity is hard

Published attempts to predict cell-line radiosensitivity from expression have performed
poorly under honest evaluation. The most directly relevant prior work, RadSigBench,
re-fitted seven published radiosensitivity signatures and benchmarked them against
resampled random gene sets, reporting a mean out-of-sample R² of 0.01 on CCLE data and
0.00 on NCI-60, with the published signatures performing no better than random gene sets
[@oconnor2022]. That result is the single most important prior for this project: it sets
the expectation that the signal is weak, and it means a near-zero R² here is a replication
rather than a surprise.

Three difficulties recur. First, **sample size**: panels with reliable clonogenic data
number in the hundreds at best, against tens of thousands of candidate features. Second,
**label noise**: literature-aggregated SF2 values combine laboratories, dose rates and
protocols; an audit of 1,672 radiobiology papers found 30.5% did not report replicates and
32.3% did not report dose rate [@oike2020]. Third, **leakage through relatedness**:
isogenic derivatives, sublines and cross-contaminated lines share molecular profiles, so a
split that separates records rather than biological entities inflates performance.

## Why public radiogenomic data

A three-line extract experiment cannot address intrinsic radiosensitivity across cell
types, but public resources can: CLARIFi aggregates literature clonogenic radiosensitivity
[@clarifi2024]; DepMap provides harmonised baseline expression for the same lines
[@depmap24q4]; Cellosaurus provides authoritative identity, problem flags and relatedness
[@bairoch2018]; and MSigDB Hallmark gene sets provide 50 compact, interpretable pathway
summaries [@liberzon2015]. Together these allow a properly grouped, prespecified benchmark
on a defensible endpoint.

## The value and the limits of interpretable machine learning

Interpretable models matter here for two reasons: a pathway-level summary is biologically
meaningful, and feature attributions can be examined for stability. But attribution has
hard limits. Permutation importance describes a *fitted model*, not biology; correlated
features share or exchange importance; and the magnitude of an importance is not a
molecular effect size. Attribution is only as trustworthy as the prediction it explains,
which is why this report caps every pathway claim at an exploratory tier when the
prediction gain is small and unvalidated.

## Rationale for prioritising candidate compounds

The original study motivates a question that the machine-learning benchmark alone cannot
answer: if cells differ in radiation response, and if some of that difference is reflected
in pathway activity, which *Moringa* constituents are worth testing experimentally? The
answer must be built from independently published chemistry and biology, compound by
compound, with the extraction solvent tracked explicitly, because the extracts of the
original study were never chemically characterised.

# Project aim and objectives

Figure 1 sets out the structure of the project and the order in which its six stages were
carried out.

![**Figure 1.** Structure of the project, from the original *Moringa oleifera* radiobiology investigation to the prioritisation of candidate constituents for future experimental work. Box fills distinguish data sources, computational steps, literature curation and proposed future work; they do not indicate how strong the evidence at each stage is. The Moringa measurements are the biological motivation only: they are never used as training, calibration or validation data, because crystal-violet proliferation under extract treatment and clonogenic survival at 2 Gy are different endpoints. Stage 6 is a proposal, not completed work.](../../figures/png/fig_01_project_workflow.png){#fig:01 width=100%}

**Aim.** To build a reproducible, auditable research pipeline that connects the original
*Moringa oleifera* irradiation study to a transparent, explainable benchmark of cellular
radiosensitivity prediction on public radiogenomic data, and to use that benchmark,
together with curated published evidence, to produce a traceable and explicitly
exploratory shortlist of candidate constituents and a feasible experimental validation
strategy.

| # | Objective | Status |
|---|---|---|
| 1 | Extract and document the original manuscript's methods and results, with every unreadable or absent item marked as such | **Completed** (`docs/moringa_scientific_linkage.md`) |
| 2 | Assemble a provenance-tracked analysis dataset linking clonogenic SF2 to baseline expression, with cell-line identity and relatedness resolved | **Completed**; 241 records, 237 components |
| 3 | Prespecify and execute a grouped, nested cross-validated comparison of five models on a single named endpoint | **Completed**; 250/250 model-fold tasks |
| 4 | Quantify the predictive gain of expression features beyond tissue of origin, and report it with its limitations | **Completed**; descriptive estimate only |
| 5 | Rank Hallmark gene-set scores by held-out permutation importance, under prespecified evidence gates | **Completed**; capped at tier C |
| 6 | Triage cell lines whose measured radiosensitivity the model reproduces least well, separating technical from biological explanations | **Completed** |
| 7 | Curate *M. oleifera* seed and leaf constituents and their radiation-response evidence from primary sources, tracking the extraction solvent | **Completed**; Tables C1, C2 and C4 |
| 8 | Implement a transparent 0–8 point prioritisation fixed before computation, and produce the ranked shortlist | **Completed**; 18 compounds ranked, 5 in tier A |
| 9 | Validate the comparison with a coverage simulation and negative controls | **Deferred**, by recorded protocol deviation (§7); three other robustness analyses were executed instead |
| 10 | Specify a feasible experimental validation strategy | **Completed** as a proposal (§10) |

Table: Project objectives and their status.

Objectives 1–8 and 10 are complete. Objective 9 is deferred, and the report states
everywhere what that costs.

# Data sources and resources

| Resource | Release | Identifier | Licence | Role |
|---|---|---|---|---|
| Original Moringa manuscript | Unpublished scan, 8 PDF pages | SHA-256 `7f644f55…e870fb9` | Redistribution **not** authorised | Biological motivation only |
| CLARIFi radiosensitivity | v1.0 | Data DOI 10.5281/zenodo.20710748; paper DOI 10.1111/cas.16334 | **CC BY-NC 4.0** | Outcome: mSF2 |
| DepMap | 24Q4 Public | DOI 10.25452/figshare.plus.27993248.v1 | CC BY 4.0 | Baseline expression, cell-line metadata |
| Cellosaurus | r56.0 | DOI 10.26037/yareta:lbz6rhlaavbldmavv4k5jdaphe | CC BY 4.0 | Identity, problem flags, relatedness |
| MSigDB Hallmark | 2025.1.Hs | Paper DOI 10.1016/j.cels.2015.12.004 | MSigDB licence terms | 50 pathway features |
| PubChem, Europe PMC, Crossref | Accessed 2026-10-22 | — | Public APIs | Compound identity and literature verification |

Table: Data resources, releases, identifiers and licences.

Every raw file carries a manifest in `data/manifests/` recording source, DOI, URL, access
date, retrieval method, SHA-256, size, column meanings, units, endpoint definition and
transformations; loaders verify checksums and stop on mismatch. The outcome file, the
expression matrix, the Hallmark GMT and the quality-control outputs were all checksum-
verified against their pinned values before the analysis run.

**Licensing caveats, stated rather than concealed.**

- **CLARIFi is CC BY-NC 4.0** (non-commercial), confirmed from both the Crossref licence
  record and the Europe PMC full text. The raw file is kept out version control, and both
  the data DOI and the licence must be cited in any publication. Non-commercial terms
  constrain downstream reuse and must be checked before any commercial application.
- The **Hallmark GMT** was downloaded manually, so there is no acquisition-log entry or
  published checksum file for it. Its local content was verified (48,689 bytes, 50 unique
  `HALLMARK_` sets, standard layout, SHA-256 `f22066af…cbbdd8e9`), but **source identity
  remains pending** the investigator's comparison against the official URL.
- The **original manuscript may not be redistributed**; only its checksum manifest and the
  extraction record are tracked.
- Compound curation used only public databases and published literature; no licensed
  chemical database was queried.

# Methodology

## Original experimental context

The manuscript was read page by page and every item labelled as a measured result, an
authors' interpretation, this project's commentary, or not stated. Nothing absent was
reconstructed. The radiobiologist reviewer checked every extracted item against the page
images. Internal inconsistencies were recorded as printed rather than silently corrected:
the extract concentration appears as 25–50 µg/mL in the abstract, 30–50 mg/mL in the
results and above 20 µg/mL in the discussion; the species of V79 is described variously as
hamster, murine and rodent; and the tabulated integrated areas are all positive although
the plotted optical-density changes are mostly negative for the two carcinoma lines, which
cannot be reconciled without the missing pages or the raw data.

## Acquisition and harmonisation of public datasets

Outcome, expression, identity and pathway resources were acquired by the investigator
under recorded provenance, parsed into separate per-endpoint tables, and harmonised on
DepMap identifiers. Download code was written only after each source had been verified.
Raw files are immutable; no value was invented or silently imputed, and missingness is
documented.

## Cell-line matching and eligibility

Cell lines were matched by stable identifiers, never by name. Cellosaurus records supplied
accessions, synonyms, problem flags, and hierarchy and origin links used to detect
relatedness. Eligibility required a usable clonogenic SF2 value, a matched baseline
expression profile and a resolved identity. The result is **241 eligible records**
spanning 20 tissues.

## Endpoint and feature definition

The single primary endpoint is **CLARIFi mSF2**, the literature-median clonogenic
surviving fraction at 2 Gy, analysed on its raw scale. Predictions are clipped to [0, 1] by
a prespecified rule; outcomes are never clipped. Features are tissue of origin
(OncotreeLineage), an optional proliferation covariate, and 50 Hallmark gene-set scores
computed from baseline expression. Crystal-violet proliferation, cell viability, ATP-based
integral survival and differential expression are kept strictly separate from clonogenic
SF2 throughout the codebase and the documentation.

## Grouping and cross-validation design

Records of cell lines related by identity (isogenic derivatives, sublines, documented
relatedness) were merged into **237 independent biological components**, and every split is
grouped by component, so related lines can never straddle a train/test boundary. Seven
components contain more than one record. Splits are stratified by tissue; the nine tissues
with at least ten components each form their own stratum and the remaining eleven are
pooled. Validation is **ten repeats of five-fold cross-validation**, with an inner
five-fold loop for tuning. All preprocessing, scaling, gene-set scoring and
hyperparameter selection occur **inside training folds only**. Metrics are
component-weighted, so a component with several records does not count more than once.
Seeds are recorded in the configuration.

A dedicated leakage audit covered identifier handling, component construction and split
construction; its findings are recorded in the decision log.

## Model development and evaluation

Five models were prespecified, from simple to rich, and scikit-learn baselines were used
before any complex architecture:

| Model | Features |
|---|---|
| M0 | Global mean |
| M1 | Tissue of origin only |
| M1P | Tissue + proliferation |
| **M2** | **Tissue + 50 Hallmark expression scores** (primary) |
| M2P | Tissue + proliferation + Hallmark scores |

Table: The five prespecified models.

M2 contains M1 as an offset, so the comparison asks specifically what expression adds
beyond tissue. The primary estimand is the **paired, component-weighted difference in mean
absolute error**, ΔMAE = MAE(M1) − MAE(M2), averaged over components within a repeat and
then over repeats. MAE, RMSE and out-of-sample R² are reported for every model, and no
metric was selected after seeing results. A random-forest extension (M3) is configured as
an explicitly post-hoc exploratory addition and cannot replace M2 as the primary benchmark
whatever its score.

## Explainability

For every real-data fit of M2 (50 fits: ten repeats × five folds), grouped permutation
importance was computed on **outer-test rows only**, using the saved model, with 20
permutations per feature. Nothing was refitted. Coefficient sign consistency across fits
and the Spearman correlation between gene-set scores were also computed, the latter so
that shared signal between correlated sets is visible rather than hidden.

## Pathway prioritisation

Gene sets were ranked under evidence gates frozen before the run. Tier A requires
significance against both null models plus high sign consistency and a high share of fits
with positive importance; tier B requires significance against the permuted-outcome null;
tier C requires only that importance exceeded zero in at least half the fits and that the
set received a non-zero coefficient in at least half. **Both higher tiers are gated on a
formally demonstrated prediction gain and at least 1,000 completed null draws.** Neither
exists in this run, so tiers A and B were unreachable by construction, and the tier
definitions were not altered to produce more impressive rankings.

## Cell-line triage

Each measured line was characterised by the absolute error of its repeat-averaged
out-of-fold prediction under M1 and M2, the spread of its prediction across repeats, and
the disagreement between the two models, each expressed as a cohort percentile. Technical
flags (stranded RNA profile, related lines in the cohort, a Cellosaurus problem flag on a
relative, small tissue group, unstable prediction, strong model disagreement) are recorded
separately from tier, so a large residual arising from a data or identity problem is never
presented as a biological discrepancy.

## Moringa compound-evidence curation

Constituents and their biology were curated separately, by literature search and reading
only, into two strictly validated files. Only *primary* studies count: a review citing an
earlier study is never independent confirmation. Only studies of the **purified compound**
can score; a study that dosed an extract is recorded with its score contribution disabled.
Only **ionising** radiation qualifies as radiation evidence, so the large UV
photoprotection literature is excluded. Nanoparticle and metal-conjugate formulations are
excluded because the carrier confounds the compound, and chemically distinct derivatives
are never credited to the parent compound. Critically, **the extraction solvent of each
report is recorded verbatim**, and compounds are classified as documented in a
dichloromethane extract, documented in seed or leaf with another solvent, or indirect and
unconfirmed. Every DOI was verified against Europe PMC or Crossref and every identifier
against PubChem, with the verification route and the reading depth stored per record.

## Candidate ranking and evidence integration

Four dimensions, fixed before any score was computed: strength of verified Moringa
constituent evidence (0–2), relevance to supported radiation-response biology (0–3),
independent source support (0–2) and feasibility of follow-up (0–1). Research groups are
counted once across both evidence files, so repeated work from one laboratory is one
source. **Chemical-class analogy earns no points.** A compound with no primary Moringa
identification is *not assessable* and never enters the shortlist, however interesting its
biology. Evidence that a compound protects *tumour* cells from radiation, or is itself
genotoxic, is a liability that is displayed and caps the tier at C. Extraction-specific
evidence is reported beside the score and never folded into it. The full rules, including
deterministic ordering and tie-breaking, are in `docs/compound_protocol.md`.

Model-associated pathways, literature-supported processes and their overlap are kept
apart. An overlap between the genes a published experiment measured and the members of a
model-ranked gene set marks a hypothesis to test; it is not evidence that the compound
modifies the gene set, the pathway, or clonogenic SF2.

## Reproducibility and quality assurance

Python ≥ 3.11, `src/` layout, type hints, small pure functions, YAML configuration with
recorded seeds and no machine-specific paths. Every analytical output carries a run record
with the git commit and a dirty-tree flag, configuration checksum, input and output
checksums, package versions and UTC timestamps; runs refuse a dirty tree. Result folders
and figures are write-once, so a published number can never be silently overwritten.
Specialist reviewers (research director, radiobiologist, radiogenomics curator, ML
methodologist, statistical reviewer, software architect, reproducibility auditor, figure
editor, literature reviewer) were consulted at the decision points recorded in
`docs/decision_log.md`, and unresolved disagreements are recorded there rather than
closed. A project safety rule prohibits automated execution of model fitting, tuning,
prediction, explainability or analysis pipelines: all such computation is run by the
investigator.

# Results

## Dataset characteristics

The analysis cohort comprises **241 eligible records forming 237 independent biological
components** across 20 tissues (Figure 2a; Table 1). Nine tissues have at least ten
components and form their own cross-validation strata: Lung (46), CNS/Brain (23),
Esophagus/Stomach (23), Bowel (21), Head and Neck (18), Breast (17), Pancreas (16),
Bladder/Urinary Tract (11) and Ovary/Fallopian Tube (10). The remaining eleven tissues,
from Skin (9) down to Biliary Tract (1), are pooled. Seven components contain more than one
record, and seven profiles are flagged as stranded RNA preparations.

Observed mSF2 spans almost the whole available interval, and tissue medians differ
visibly (Figure 2b), which is why a tissue-only model is the right baseline against which
to judge expression features. MCF-7 (observed mSF2 0.52) and DU145 (0.71) both lie within
the cohort, and are shown as context only; V79 is a Chinese hamster line and has no
counterpart in this human cohort.

![**Figure 2.** Composition and radiosensitivity of the analysed cohort (241 eligible records, 237 independent biological components). (a) Independent components per tissue (OncotreeLineage); the dashed line marks the ten-component threshold above which a tissue formed its own cross-validation stratum. (b) Distribution of observed CLARIFi mSF2, the literature-median clonogenic surviving fraction at 2 Gy, with one point per independent component so that related cell lines count once; tissues with fewer than ten components are pooled. Boxes show the median and interquartile range; whiskers extend to 1.5 times the interquartile range. Open diamonds mark MCF-7 and DU145, two of the three lines used in the motivating Moringa study, shown as context only: no statement about Moringa extracts or radioprotection is made or implied. V79 is a Chinese hamster line and has no counterpart in this human cohort.](../../figures/png/fig_02_dataset_composition.png){#fig:02 width=100%}

## Model-performance comparison

| Model | MAE | RMSE | Out-of-sample R² |
|---|---:|---:|---:|
| M0 global mean | 0.133624 | 0.170755 | −0.009497 |
| M1 tissue only | 0.134228 | 0.171494 | −0.018275 |
| M1P tissue + proliferation | 0.134259 | 0.171304 | −0.016026 |
| **M2 tissue + expression** | **0.130397** | **0.169115** | **+0.009347** |
| M2P tissue + proliferation + expression | 0.130388 | 0.168841 | +0.012822 |

Table: Component-weighted out-of-fold performance of the five prespecified models; MAE and RMSE in mSF2 units. Calibration and paired differences are in Table 2.

Two results stand out (Figure 3; Table 2). First, **expression features reduce the error, and the
reduction is small**: ΔMAE = 0.00383 mSF2 units against the tissue-only baseline, 2.85% of
that baseline's MAE, with the richer model achieving the lower error in **nine of ten**
cross-validation repeats (the exception, repeat 7, favours M1 by 0.0024; Table S1). The
proliferation-adjusted sensitivity comparison agrees in direction and size (ΔMAE =
0.00387, favouring the richer model in ten of ten repeats). Second, **no model predicts
well**: out-of-sample R² ranges from −0.018 to +0.013, so every model is approximately as
accurate as predicting the cohort mean, and the tissue-only model is marginally *worse*
than the global mean on MAE and R².

![**Figure 3.** Out-of-fold predictive performance of the five prespecified models (M0 global mean, M1 tissue only, M1P tissue and proliferation, M2 tissue and 50 Hallmark expression scores, M2P tissue, proliferation and expression). (a) Component-weighted mean absolute error, in mSF2 units, with bars starting at zero. (b) Out-of-sample R-squared, where zero corresponds to predicting the training-set mean; every model lies close to zero, so none explains much of the variation between cell lines. (c) Paired difference in MAE in each of the ten cross-validation repeats for the primary comparison (M2 against M1) and the proliferation-adjusted sensitivity comparison (M2P against M1P); positive values favour the richer model. The thick vertical bar is the pooled estimate, the mean over repeats. The upper axis expresses the same difference as a percentage of MAE(M1). Repeats re-split the same 237 components, so their spread shows split-to-split variability, not sampling uncertainty; no interval is shown because no interval method was validated for this design. All values are component-weighted out-of-fold values from ten repeats of five-fold cross-validation grouped by biological component and stratified by tissue, with all tuning and scaling inside training folds. Descriptive only: superiority was not formally assessed and negative-control draws were not run.](../../figures/png/fig_03_model_performance.png){#fig:03 width=100%}

**Reconciliation of the reported difference.** Three saved files report the primary
difference, and they agree exactly once the estimand is named:

| Source | Value | Estimand |
|---|---:|---|
| `comparisons.csv` → `delta_mae` | 0.0038316558867076 | Paired, **component-weighted**, mean over repeats (**primary**) |
| `model_metrics.csv` → MAE(M1) − MAE(M2) | 0.0038316558867076 | Difference of the two component-weighted MAEs |
| `per_repeat_delta_mae.csv` → mean of 10 repeats | 0.0038316558867076 | Mean of the ten per-repeat values |
| `comparisons.csv` → `record_weighted_delta_mae` | 0.0038170756763974 | Paired, **record-weighted** (each of 241 records weighted equally) |

Table: The primary difference as reported by three saved output files.

The first three are the same quantity computed three ways and agree to all reported
digits. The fourth differs by 1.5 × 10⁻⁵, which is 0.4% of the estimate; it is **not a
discrepancy but a different weighting**, giving components with several records more
influence. The protocol specifies the component-weighted estimate, so that is what this
report uses throughout, and the record-weighted value is reported alongside rather than
chosen for being marginally different. The relative figure, 2.85%, is
0.0038317 / 0.1342282.

**What this comparison does and does not establish.** It is a descriptive estimate.
Superiority was **not formally assessed**: the coverage simulation that would have
validated an interval method was deferred (§7), so `comparisons.csv` reports no interval
and no p-value, and the saved evaluation record states the inference status explicitly. No
negative-control draws were run, so the gain cannot be compared against a permuted-outcome
or random-gene-set reference. Repeated cross-validation is **not** external validation: the
ten repeats re-split the same 237 components, so their spread measures split-to-split
variability, not sampling uncertainty, and it cannot tell us how the model would behave on
an independent cohort.

## Why the out-of-sample R² stays near zero

Figure 4 shows the mechanism directly. Predictions from both M1 and M2 occupy a narrow band
close to the cohort mean, while the observations span almost the entire interval. The
models are therefore not miscalibrated so much as uninformative: they shrink heavily
towards the mean because the features support little more than that. Calibration slopes
confirm this reading, moving from −1.21 for M1 and −4.00 for M0 to 0.65 for M2 and 0.63 for
M2P; the strongly negative slopes of M0 and M1 are an artefact of their predictions being
constant within a tissue, discussed below.

![**Figure 4.** Why the out-of-sample R-squared stays near zero. (a, b) Observed against out-of-fold predicted mSF2 for the tissue-only model M1 and the tissue-plus-expression model M2. Each point is one independent biological component; records of a component are averaged and each record's prediction is already the mean over the ten cross-validation repeats, so no cell line contributes more than one point. The dashed line is the identity; both axes span the full possible range of the endpoint. (c) Empirical cumulative distributions of the observed values and of the predictions of both models. The predictions of both models occupy a narrow band near the cohort mean while the observations span almost the whole interval, which is the behaviour of a model with little usable signal rather than of a miscalibrated one. No trend line is fitted. Descriptive only.](../../figures/png/fig_04_prediction_behaviour.png){#fig:04 width=100%}

## Repeat-level and tissue-level behaviour

Across the nine well-supported tissues, M2 achieves the lower error in **eight**
(Figure 5; Table 3). The largest improvements are in Ovary/Fallopian Tube (0.0112), Breast (0.0084)
and Head and Neck (0.0075). The exception is instructive: in **Pancreas, M2 is worse by
0.0110**, which is nearly three times the size of the overall gain. A pooled improvement
of this magnitude is therefore not uniform, and it would be misleading to present it as a
general property of the model. Tissues with fewer than ten components are excluded from
this figure because their estimates are unstable.

![**Figure 5.** Performance by tissue of origin, for the nine tissues with at least ten independent components; the number of components is given beside each tissue name. (a) Component-weighted out-of-fold MAE of each model, in mSF2 units; lighter cells are lower error. (b) The difference MAE(M1) minus MAE(M2) for the same tissues, in the same row order; positive values (blue) mean the expression model had the lower error. Differences are small relative to the errors themselves and are descriptive only: they come from one cross-validated run, no per-tissue inference was performed, and tissues with fewer than ten components are omitted here because their estimates are unstable.](../../figures/png/fig_05_tissue_performance.png){#fig:05 width=100%}

Prediction stability across repeats (Figure S1) is higher for the tissue-only models,
whose prediction is a shrunken tissue mean, than for the expression models, as expected.

**A reporting correction.** The first version of the within-tissue Spearman analysis
reported strongly negative rank correlations for M1 in all nine larger tissues. Code
inspection established the cause: every fitted M1 predicts a single value per tissue — the
shrunken training-fold tissue mean — so a held-out line's pooled out-of-fold prediction is
effectively the mean of the *other* lines of its tissue, which falls as the line's own
value rises. This is a leave-fold-out mean artefact, not a biological finding; the
statistic measures no within-tissue ranking at all for M0 and M1. The corrected table
(Table S4) reports the statistic as undefined when a model's prediction is constant within a tissue,
and defined values carry an explicit downward-bias caveat. **The original pooled
within-tissue correlations are not interpreted as evidence anywhere in this report**, and
the version-1 table is retained unchanged for audit.

## Explainability findings

All 50 M2 fits completed and were analysed. Ranked by mean held-out permutation importance
(Figure 6a; Table S2), the leading gene sets are **HALLMARK_P53_PATHWAY** (mean importance 0.00343,
positive in 90% of fits, sign consistency 0.92, dominant sign negative), followed by
COMPLEMENT (0.00118), OXIDATIVE_PHOSPHORYLATION (0.00107), UV_RESPONSE_UP (0.00100),
MYC_TARGETS_V2, KRAS_SIGNALING_UP and UV_RESPONSE_DN.

Three observations matter more than the ranking itself. First, the **magnitudes are tiny**:
the largest mean importance, 0.0034 mSF2 units, is of the same order as the entire
predictive gain, so the ranking is describing a very small effect. Second, **stability is
modest**: across the 50 fits the mean Kendall τ between importance rankings is 0.225, mean
rank-biased overlap 0.518, and mean top-10 Jaccard index 0.391 — the same gene sets do
*not* reliably appear at the top of every fit. Third, **correlated sets share signal**:
several ranked sets are flagged as correlated with another set at |ρ| ≥ 0.80 (Figure S2),
including COMPLEMENT with APOPTOSIS and MYC_TARGETS_V2 with MYC_TARGETS_V1, so importance
may be shared or exchanged between them rather than attributable to one.

![**Figure 6.** Exploratory importance of the Hallmark gene-set scores in the expression model M2. (a) The fifteen highest-ranked gene sets. Grey points are the grouped permutation importance in each of the fifty model fits (ten repeats by five folds), computed on held-out rows only as the increase in component-weighted MAE when a score is permuted across components; the diamond is the mean over fits, coloured by the prespecified triage tier. The spread across fits is split-to-split variability, not a confidence interval. (b) The two criteria that define tier C, for all fifty gene sets: the share of fits in which importance exceeded zero, and the share of fits in which the set received a non-zero coefficient. The shaded corner is the region satisfying both thresholds (dashed lines, 0.50 each), as frozen in configs/triage.yaml. Tiers A and B were unreachable by design: they require a formally demonstrated prediction gain and at least 1000 negative-control draws, and neither exists in this run. Shares are proportions of overlapping cross-validation fits, not probabilities or p-values. These rankings describe one fitted model family on one dataset. They are not validated biomarkers, causal mechanisms, radiation-response pathways, or molecular effect sizes, and correlated gene-set scores can share or exchange importance.](../../figures/png/fig_06_gene_set_importance.png){#fig:06 width=100%}

We note explicitly that **DNA repair, G2M checkpoint and hypoxia were *not* among the
prioritised sets**, although they are the pathways a radiobiologist would expect: G2M
checkpoint ranked 13th with importance positive in only 8% of fits, and hypoxia 10th with
10%. Reporting this is a safeguard against the temptation to present a familiar
radiation-response narrative that the data do not support.

## Pathway shortlist

Seven of 50 gene sets reached **tier C** and 43 were not prioritised; **no set reached
tier A or B**, because both require a formally demonstrated prediction gain and at least
1,000 negative-control draws, and the run has neither (Figure 6b). The gene-set tests
record zero completed draws of both the permuted-outcome and random-gene-set nulls, so
attribution is not permitted and the stability gate is infeasible.

What the shortlist represents: these are the gene-set scores whose permutation importance
was positive in at least half of the cross-validation fits and which received a non-zero
coefficient in at least half, within one model family on one dataset. What it does not
establish: it is not a gene-level finding, a validated biomarker, a causal mechanism, a
radiation-response pathway, or a molecular effect size, and it is not evidence that
modulating the pathway would change radiosensitivity.

## Cell-line discrepancies

Of 241 measured lines, 12 reached tier A, nine tier B and 27 tier C; 193 were not
prioritised (Figure 7; Table S3). The highest-ranked discrepancies are dominated by lines with
extreme observed values — HT-144 (observed 0.08, predicted 0.59), KNS-42 (0.125 vs 0.59),
HEC-1-B (0.97 vs 0.57), D283 Med (0.18 vs 0.59) — which is the shrinkage mechanism of
Figure 4 seen one line at a time rather than a set of biologically unusual cell lines.

The triage separates the possible explanations. Of the tier A and B lines, several carry
technical flags (small tissue group, related lines in the cohort, stranded RNA profile) and
are routed to technical review first; the remainder are labelled as unexplained
discrepancies requiring follow-up. Because tier thresholds are cohort percentiles, roughly
the stated top fraction is always flagged: a flag means "relatively large in this cohort",
not "abnormal".

Of the two Moringa context lines, **MCF-7 was not prioritised** (its held-out errors lie
within the bulk of the cohort: observed 0.52 against 0.574 under M1 and 0.534 under M2),
and **DU145 reached tier C** with the technical flags stranded RNA profile, small tissue
group, unstable prediction across repeats and strong model disagreement (observed 0.71
against 0.580 under M1 and 0.650 under M2). Their tiers were assigned by the same rule as
every other line and were not adjusted for their relevance to the motivating study. **No
individual prediction error is evidence of radioprotection, radiosensitisation or any
causal mechanism**, and lines selected for extreme residuals are expected to agree better
on re-measurement even if nothing is wrong, through regression to the mean.

![**Figure 7.** Cell lines whose measured radiosensitivity the model reproduces least well. (a) Residual (observed minus predicted mSF2 under M2, predictions averaged over repeats) against the observed value, for every measured line, coloured by prespecified discrepancy tier; triangles mark lines carrying at least one technical flag. The strong dependence of the residual on the observed value is shrinkage: because the models predict close to the cohort mean, lines with extreme measured values necessarily have the largest residuals. Circled points are MCF-7 and DU145, labelled because of their relevance to the motivating study; their tiers are not altered. (b) Flags recorded for the tier A and tier B lines, in rank order: flags concerning prediction behaviour (instability across repeats, disagreement between M1 and M2) are distinguished from flags concerning the data or the cell-line identity (stranded RNA profile, related lines in the cohort, a Cellosaurus problem flag on a relative, small tissue group). Tier thresholds are cohort percentiles, so a flag means "relatively large in this cohort", not "abnormal". These are measured CLARIFi lines used in model development, not independent validation samples; a large residual is a signal to re-check identity, data provenance and the original measurement, and is not evidence of unusual radiobiology, radioprotection or radiosensitisation. Lines selected for extreme residuals are expected to agree better on re-measurement even if nothing is wrong (regression to the mean).](../../figures/png/fig_07_cell_line_discrepancies.png){#fig:07 width=100%}

## Verified Moringa constituents

Curation produced a provenance-carrying inventory of *M. oleifera* seed and leaf
constituents drawn from primary analytical studies, with each report's extraction solvent,
identification method, DOI verification route and reading depth recorded (Table C1). Three
findings are substantive in themselves.

**First, only one constituent is confirmed in the extraction solvent the original study
actually used.** Abdelsayed, Abdel Motaal and Hanafi [-@abdelsayed2021jfda] isolated
**niazimicin**, a thiocarbamate glycoside, from the **seed methylene-chloride fraction**,
confirmed its structure by HRMS, UV, IR, EI-MS and 1D/2D NMR, and quantified it by
validated UPLC-MS/MS in both the seed and the leaf CH₂Cl₂ fractions. The same study did
*not* detect niazirin or glucomoringin there. The only other dichloromethane-specific
identifications are GC-MS spectral-library matches in leaf DCM material, read at abstract
level: 4-hydroxyphenylacetonitrile and methyl 4-hydroxyphenylacetate
[@mohdfisall2021], and palmitic acid and cis-vaccenic acid [@khandelwal2019] — the latter
in a journal indexed in neither PubMed nor Europe PMC, with the full compound list
inaccessible, and with an identity that electron-impact library matching cannot settle,
since it cannot distinguish Δ9 from Δ11 C18:1 isomers without authentic standards.

**Second, the identification evidence for several widely cited "Moringa compounds" is much
weaker than their reputation suggests, and for one of them absent.** Free quercetin and
kaempferol aglycones rest only on tentative LC-HRMS dereplication without authentic
standards, and may in any case form by hydrolysis of the abundant glycosides during
extraction; the forms that primary analytical work actually establishes in leaf are the
**glycosides** — isoquercitrin, astragalin and rutin. Under the prespecified rules those
tentative aglycone reports are still primary seed or leaf reports, so quercetin and
kaempferol **are assessable**, but only in the weakest identification band (one point of
two), and the pharmacokinetic caution applies in both directions: aglycone evidence may not
be transferred to a glycoside, nor the reverse, without explicit justification. Benzyl
isothiocyanate is **not** a documented
seed or leaf constituent: its precursor, benzyl glucosinolate, is reported in *roots*,
while seed and leaf carry the rhamnosyloxy-benzyl glucosinolate instead. Gallic acid and
caffeic acid yielded no primary report in *M. oleifera* seed or leaf at all and so do not
appear in the inventory.

**Third, identifier hygiene was not a formality.** Four public records that a name search
returns are wrong or ambiguous for this purpose, and using them would have propagated an
error: the mis-structured carbamate record (C16H23NO8, with the ethoxy group on the
sugar), a "niaziminin A" record whose structure is not the thiocarbamate, a
stereochemistry-free niazimicin record, and glucomoringin, for which *every* available
record is a potassium salt with a different stereo-InChIKey and none could be matched to
the natural structure. The last remains **unresolved** and is flagged for the investigator.

## Candidate-compound shortlist

The evidence linking these constituents to radiation-response biology was curated
separately, from primary studies of purified compounds only (Table C2), and the
prespecified score was then applied (Table C3, Figures 8 and 9). **Eighteen compounds
entered the ranked shortlist and five reached tier A**; three further constituents scored
below the tier-C threshold and were not ranked, and benzyl isothiocyanate was not
assessable.

| Rank | Compound | D1 identity | D2 radiation biology | Total | Tier |
|---:|---|---:|---:|---:|---|
| 1 | α-Tocopherol | 2 | 3 | 8 | **A** |
| 2 | Chlorogenic acid | 1 | 3 | 7 | **C** (capped) |
| 3 | Kaempferol | 1 | 3 | 7 | **A** |
| 4 | Quercetin | 1 | 3 | 7 | **A** |
| 5 | Rutin | 1 | 3 | 7 | **A** |
| 6 | β-Sitosterol | 1 | 3 | 7 | **A** |
| 7 | Niazirin | 2 | 1 | 6 | B |
| 8 | Oleic acid | 1 | 2 | 5 | B |
| 10 | Moringin | 1 | 1 | 5 | B |
| 13 | Niazimicin | 2 | 0 | 4 | C |
| — | Benzyl isothiocyanate | 0 | 3 | 6 | **not assessable** |

Table: Candidate-compound ranking, abbreviated (D1 and D2 are two of the four scoring dimensions).

(Abbreviated; ranks 9, 11, 12 and 14–18 are in Table C3, together with every point's
written justification.)

Three features of this table matter more than the ordering.

**The liability cap did real work.** Chlorogenic acid scored 7 of 8 — equal to four tier-A
compounds — and is nevertheless held at tier C, because one primary study reports that it
*protects hepatocellular carcinoma cells* from radiation. A score alone would have
promoted it; the prespecified cap prevented that.

**The exclusion rule did real work.** Benzyl isothiocyanate scored 6 on biology and
sources, and is still **not assessable**, because it has no primary report as a seed or
leaf constituent (its precursor is a root glucosinolate). It cannot be ranked however good
its radiation evidence is.

**The mismatch the curation predicted is visible in the ranking.** Niazimicin holds the
only full identity score among compounds confirmed in a dichloromethane fraction (D1 = 2)
and scores **zero** on radiation biology, so it sits at tier C. Moringin, the signature
Moringa isothiocyanate, reaches only tier B. Meanwhile four of the five tier-A compounds
hold D1 = 1 — a spectral-library or dereplication match — and none of the five has been
verified in a dichloromethane extract.

What the curated evidence establishes, and what Figures 8 and 9 display, is the following.

- **Moringin, the isothiocyanate most characteristic of *Moringa*, has no ionising-radiation
  study whatsoever.** Exhaustive searching found zero primary studies combining moringin or
  glucomoringin with ionising radiation. Its evidence is confined to non-radiation cell
  work: pro-apoptotic effects with p53, CDKN1A, BAX and caspase involvement in neuroblastoma
  [@cirmi2019] and G2/M arrest in prostate cancer cells [@abdkarim2023], NRF2 activation in
  a motor-neuron model [@gugliandolo2024], and NF-κB inhibition with a myeloma xenograft
  [@brunelli2010]. Because chemical-class analogy earns no points by design, moringin gains
  nothing from the benzyl isothiocyanate radiation literature, and the report presents that
  analogy as an untested hypothesis rather than as support.
- **The best-evidenced radiation candidates are not Moringa-specific.** β-Sitosterol has
  ionising-radiation normal-tissue protection evidence from two independent groups
  [@li2007; @elbakary2026]; rutin likewise [@patil2017; @thabet2018]; α-tocopherol has a rat
  crypt-microcolony clonogenic result [@felemovicius1995] and a randomised controlled trial
  of radiation mucositis [@ferreira2004]. All are documented in Moringa seed or leaf, but
  **none has been verified in a dichloromethane extract**, which is why the extraction
  column sits beside the score rather than inside it.
- **One candidate carries an explicit liability.** Chlorogenic acid has normal-tissue
  protection evidence in bone marrow [@abraham1993] and testis [@abedpour2022], but Yin and
  colleagues [-@yin2022] report that it *protects hepatocellular carcinoma cells* from
  radiation via NRF2, concluding it could hinder radiotherapy. Under the prespecified rule
  this caps its tier at C and the flag is printed. Astragalin is similarly capped: its only
  DNA-damage-relevant primary signal is *pro-genotoxic* [@saito2012], and the one
  astragalin "radiation" paper is UVB, which is not ionising radiation.
- **An informative negative was retained.** Membrane oleate enrichment did **not** alter
  the clonogenic radiosensitivity of human lymphoid cells [@george1983] — a direct
  clonogenic test, and a reason not to prioritise oleic acid despite its abundance in seed
  oil.

![**Figure 8.** Evidence-based prioritisation of documented *Moringa oleifera* seed and leaf constituents for future experimental work. (a) Points awarded in each of the four prespecified dimensions (numbers are the points; shading is the fraction of that dimension's maximum), beside the extraction-specific evidence: whether the compound has been identified in a dichloromethane extract or fraction of seed or leaf, in seed or leaf with another solvent, or only indirectly. (b) Total priority score out of eight, coloured by tier. The extraction column is deliberately kept outside the score, because the original study used dichloromethane extracts whose composition was never measured. Scoring rules were fixed before any score was computed (docs/compound_protocol.md): only primary studies of the purified compound score, chemical-class analogy earns nothing, several papers from one research group count as one source, a compound with no primary Moringa identification is not assessable, and evidence that a compound protects tumour cells from radiation or is itself genotoxic caps the tier at C. Every tier, including A, is hypothesis-generating: no tier asserts radioprotection, radiosensitisation, potency, or any effect of the extracts used in the original study.](../../figures/png/fig_08_compound_priority.png){#fig:08 width=100%}

![**Figure 9.** What the published evidence actually links each shortlisted compound to. (a) Radiation-response processes for which a primary study of the purified compound exists: symbol size is the number of independent research groups, and colour distinguishes studies using ionising radiation from studies of the same process without radiation. Compounds are in priority order. An empty row means no qualifying primary study was located, which is a gap in the literature, not evidence of no effect. (b) Where recorded, the number of genes a published experiment measured for the compound that are also members of a Hallmark gene set ranked by the exploratory explainability analysis; blank cells mean no overlap was recorded. Such an overlap marks a point where a compound and a model-highlighted gene set touch the same genes. It is a hypothesis to be tested, not evidence that the compound modifies the gene set, the pathway or clonogenic SF2, and the gene-set ranking it refers to was itself capped at tier C. Reported directions (protection or sensitisation, and the cell type involved) are given in Table C2 and are never merged.](../../figures/png/fig_09_compound_evidence_map.png){#fig:09 width=100%}

**Figure 8 makes the central mismatch visible in a single panel.** Reading panel (a) down
the extraction column and across the four scoring dimensions, the Moringa-specific
compounds with the darkest identity cell — niazimicin, glucomoringin, niazirin,
niaziminin, the acetylated isothiocyanate and the carbamate glycoside, all scoring the full
two points for a structurally confirmed presence in Moringa seed or leaf — are precisely
those whose radiation-biology cell is empty or nearly so. The one compound with full
scores on both identity and radiation biology is α-tocopherol, a ubiquitous plant
metabolite that has not been found in a dichloromethane extract. The compounds with a full
radiation-biology score sit in the opposite pattern: four of the five tier-A compounds
carry only one identity point, from a spectral-library or dereplication match, and the
extraction column shows that none of them has been found in a dichloromethane extract.
Panel (b) shows the consequence of the liability rule in the bar lengths: chlorogenic
acid's total reaches 7, the same as four tier-A compounds, yet its bar is coloured as
tier C. **A reader comparing bar lengths alone would rank it among the leaders; the
prespecified cap is what prevents that, and the figure is drawn so the discrepancy is
visible rather than hidden.**

**Figure 9 shows how thin the biological evidence is once it is attributed compound by
compound.** In panel (a) the dot size is the number of independent research groups and the
colour separates studies that used ionising radiation from studies of the same process
without it. Only a minority of cells are filled at all, and several shortlisted compounds
have no ionising-radiation dot anywhere on their row: moringin, the most
Moringa-characteristic candidate, appears only in the non-radiation colour, and niazimicin
has no scored row at all because its one study dosed an extract fraction rather than the
purified compound. Panel (b) is deliberately sparse: only 25 compound-by-gene-set
overlaps were recorded (Table C4), 23 for shortlisted compounds and two for benzyl
isothiocyanate, which is not assessable and is not shown. They link the genes a published
experiment actually measured to the members of a tier-C Hallmark set, and they are small:
14 involve a single gene and 9 involve two; the largest are moringin with the p53 pathway
(three genes) and quercetin with the p53 pathway (five genes). Those overlaps are the
thinnest kind of link in the project — a point where a compound and a model-highlighted
gene set happen to touch a few of the same genes — and they are displayed at that scale
on purpose. **They mark where a hypothesis could be formed, not
where an effect has been shown.**

### What a tier means, and what it does not

A tier records **the state of the published evidence about a compound**, assembled under
rules fixed before any score was computed. It is not a measure of radioprotection, and
nothing in this ranking should be read as one.

| A tier **does** say | A tier does **not** say |
|---|---|
| Primary studies exist, of the purified compound, with the stated independence | That the compound protects or sensitises anything |
| The compound is documented in Moringa seed or leaf at the stated identification strength | That it was present in the extracts the original study tested |
| Published work connects it to a radiation-response process | That it modifies clonogenic survival, the endpoint modelled here |
| A follow-up experiment can be specified from the record | That such an experiment would succeed |

Table: What a compound tier does and does not say.

Tier A means "best documented", not "most likely to work". Four of the five tier-A
compounds are ubiquitous plant metabolites whose radiation evidence comes from outside
Moringa research entirely, and the direction of that evidence differs between them:
quercetin and kaempferol have *radiosensitisation* evidence in tumour cells as well as
normal-tissue protection, while β-sitosterol and rutin have normal-tissue protection only.
Radioprotection and radiosensitisation are opposite effects and are never merged in
Table C2.

### Realistic first-stage experimental priorities

The ranking answers "what is best documented?". A first experiment has to answer a
narrower question, so the two orderings differ, and they differ without any score being
changed. Three questions can be separated:

**1. Is any plausibly active compound actually in the extracts that were tested?** This is
the project's largest gap and the cheapest to close. The priority candidates are
**niazimicin** (tier C, the only compound with a confirmed structural identification in
the seed *and* leaf dichloromethane fractions) and **moringin** (tier B, the signature
Moringa isothiocyanate). Neither has any ionising-radiation study, so neither can be
offered as a protection candidate — they are priorities for **analytical characterisation
of the original extracts**, followed by a first radiation screen if they are found.

**2. Does a compound with existing radiation evidence act on the endpoint this project
models?** Here **α-tocopherol** is the strongest first-stage candidate: it is the only
tier-A compound with a full identity score, and it is one of only two compounds in the
whole evidence base with a *clonogenic* radiation result (rat intestinal crypt survival),
alongside a randomised trial of radiation mucositis. **β-Sitosterol** follows, with
normal-tissue protection from two independent groups. Both must be tested in matched
normal and tumour cells, because neither has a tumour arm.

**3. Which candidates should not lead?** **Chlorogenic acid** should not be a first-stage
protection candidate at all, despite its score: the tumour-protection finding makes it a
cautionary compound in a radiotherapy context. **Astragalin** is capped for the same class
of reason, its only DNA-damage-relevant evidence being pro-genotoxic. **Oleic acid** has a
direct clonogenic test showing **no** effect on radiosensitivity, so it is informative but
not a candidate. Quercetin, kaempferol and rutin are scientifically interesting but are
second-stage: their Moringa identity is a tentative dereplication, and the
aglycone/glycoside pharmacokinetic question would have to be settled first.

A defensible first-stage programme is therefore narrow: **characterise the extracts
(niazimicin, moringin), and test α-tocopherol and β-sitosterol on clonogenic survival in
matched normal and tumour cells over a dose range.** That recommendation uses the tiers as
evidence summaries, not as predictions, and it leaves every score exactly as computed.

The scientific shape of the result is therefore a **mismatch, and it is the module's most
useful output**: the compound with the best claim to being present in the extracts that
were actually tested has no radiation biology, and the compounds with radiation biology
have no confirmed presence in those extracts. Neither gap can be closed by further
literature work. Both are closed by the experiments in §10.

## The exploratory and robustness layer

The results above come from the **frozen primary benchmark**. A separate, clearly labelled
layer of analyses extends the investigation without touching it. They are listed here with
their status so that no reader can mistake a planned analysis for a finding; the plan,
with measured costs and the limits on what each may license, is
`docs/robustness_plan.md`.

| Analysis | Question | Run | Status |
|---|---|---|---|
| Random forest M3 | Does a different model family extract more signal from the same features and splits? | `exploratory_m3_v1` | **Completed**, 200/200 tasks |
| Leave-one-tissue-out | Does an expression-only model transfer to a tissue it has never seen? | `loto_v1` | **Completed**, 18/18 tasks |
| Outcome-scale sensitivity | Does the advantage survive the neglog and logit scales, or is it a raw-scale artefact? | `scales_v1` | **Completed**, 400/400 tasks |
| Negative controls, 1000 draws of each null | Is the observed advantage larger than this pipeline produces when expression cannot carry signal? Are any gene sets more important than matched random sets? | `controls_v1` | Configured; ~10–20 h at six workers; **not executed** |

Table: The exploratory and robustness layer: questions, runs and execution status.

### Results of the executed robustness analyses

**A different model family does not do better.** The random forest M3, fitted on the same
splits with the same nested tuning, reached MAE 0.13148 and out-of-sample R² +0.00643,
against M2's 0.13040 and +0.00935 (Table R1). Its gain over the tissue-only baseline, ΔMAE = 0.00275,
is **smaller** than M2's 0.00383. **M3 therefore performs worse than M2, and that is
reported as the result.** Within the same run M0, M1 and M2 reproduced `primary_v1` to the
last decimal place, which also confirms that the frozen benchmark is reproducible.

**Expression transfers weakly to an unseen tissue, and not to every tissue.** Holding out
each of the nine well-supported tissues in turn (185 components, 187 records), the
expression-only model M2X reached MAE 0.12267 and out-of-sample R² **+0.0308** against the
global mean's 0.12753 and −0.0084 (ΔMAE = 0.00487 mSF2 units). This is the only analysis
in the project in which out-of-sample R² is clearly above zero, and it is a different and
easier comparison than the primary one — expression-only against a global mean, with
tissue removed from both sides — so it is **not** comparable with the primary 0.00383 and
does not revise it. Per-tissue behaviour is uneven (Table R2; ΔMAE against the global mean,
mSF2 units): the gain is largest for Ovary/Fallopian Tube (+0.0156) and Head and Neck
(+0.0153), followed by Breast (+0.0119), Bowel (+0.0092), Bladder/Urinary Tract (+0.0079),
Lung (+0.0049) and CNS/Brain (+0.0025), and it is **negative for two tissues: Pancreas
(−0.0142) and Esophagus/Stomach (−0.0030)**. The Pancreas loss is nearly three times the
pooled gain, and Pancreas is also the one well-supported tissue in which M2 was worse
than M1 in the primary benchmark. The pooled transfer result is therefore conditional on
the tissue held out.

**The advantage is scale-dependent, and this is the most important negative finding of the
robustness layer.** Repeating the M2-versus-M1 comparison on transformed outcome scales
with 20 repeats gave ΔMAE = **0.00023 on the neglog scale** — essentially nothing, with
M2's out-of-sample R² falling to −0.0322 — and 0.00980 on the logit scale (Table R3). The direction
is preserved on all three scales, but the magnitude ranges from negligible to about two
and a half times the primary estimate depending on the transformation. The raw scale
remains the protocol's prespecified primary scale, and these results are reported beside
it rather than replacing it; together they mean the primary estimate should be read as
**small, direction-consistent and sensitive to how the outcome is expressed**.

Four rules govern this layer, and they are the reason it is kept separate.

**It cannot promote a new primary model.** M3 was configured *after* the primary results
were seen, so M2 remains the primary benchmark whatever M3 scores. In the event M3 scored
worse, which is the expected outcome for a tree ensemble on 237 components and 50 coarse
features, and which indicates that the ceiling here is set by the data rather than by the
model family.

**Consistency with the frozen run is verified mechanically, not asserted.**
`scripts/verify_run_consistency.py` checks that an exploratory run covers the same 241
records and 237 components, that no biological component straddles a training and test
fold or two inner folds, that the split table and its hash are identical to the primary
run's, that the input checksums, base seed and fold counts match, that tuning is nested,
that models shared with the primary run reproduce its predictions bit-for-bit, and that
the primary run's own files still match their recorded hashes.

**Negative controls do not by themselves create inference.** With 1000 draws the
gene-set p-values that are currently empty become available, and the observed ΔMAE can be
placed against a permuted-outcome null *descriptively*. Tiers A and B stay closed, because
that gate also requires a formally shown prediction gain, which needs the interval method
the deferred coverage simulation was to validate. A permutation test would be a legitimate
alternative route, but adopting it requires a protocol amendment recorded **before** the
null distribution is inspected; written afterwards it is a post-hoc test chosen in sight
of the result, and would have to be reported as one.

**The within-tissue correlation artefact is avoided, not revisited.** None of these
analyses reports the pooled within-tissue rank correlation that the version-1 table
produced; the corrected statistic is undefined wherever a model predicts a constant within
a tissue.

# Discussion

## What the modest improvement means

Expression features reduced the error of a tissue-only baseline by 2.85%, consistently in
direction (nine of ten repeats) but small in size and not uniform across tissues, with
Pancreas moving in the opposite direction by nearly three times the pooled gain. The
defensible interpretation is that **baseline Hallmark pathway activity carries a small
amount of information about intrinsic radiosensitivity beyond tissue of origin, on this
endpoint, in this cohort, under this model family**. It is not a demonstration that
expression predicts radiosensitivity usefully, and it is not a validated effect: no
interval, no p-value, no negative control and no external cohort stand behind it.

The executed robustness analyses sharpen this reading rather than softening it. The
advantage survives a change of model family only in the sense that a random forest does
**worse** (ΔMAE 0.00275 against M2's 0.00383), and it nearly disappears on the neglog
outcome scale (ΔMAE 0.00023), while being about two and a half times larger on the logit
scale. A result that moves by an order of magnitude with the choice of transformation is
small enough to be shaped by it. The one encouraging result is the leave-one-tissue-out
analysis, where expression alone reached out-of-sample R² +0.031 against a global mean —
the only clearly positive R² in the project — but that is an easier comparison on a
different design, and it was negative for two of the nine well-supported tissues
(Pancreas −0.0142, Esophagus/Stomach −0.0030). Pancreas is unfavourable in both the primary
and the leave-one-tissue-out analyses, so the tissue-level picture, and not only the pooled
gain, has to be part of any statement about generalisation.

Three further cautions apply. The comparison is nested (M2 contains M1 as an offset), so
the two models' errors are strongly correlated and the paired difference is the right
statistic but a narrow one. Repeated cross-validation re-splits one fixed set of
components, so it cannot estimate generalisation to new cohorts. And the direction of the
result should not be over-read from the baseline's own behaviour: M1 is marginally worse
than the global mean M0 on MAE, which indicates that tissue of origin, as encoded here,
contributes little once shrinkage is accounted for.

## Why out-of-sample R² remains low

Figure 4 shows predictions compressed near the cohort mean against observations spanning
the full interval. Several causes act together, and they are not separable with these data.
The **label** is a literature median aggregating laboratories, dose rates and protocols,
and the field's own reporting audit found a third of papers omitting replicates or dose
rate [@oike2020]; CLARIFi supplies one median per line, so per-line assay variability
cannot even be estimated. The **sample** is small (237 independent components) and
tissue-imbalanced. The **features** are 50 coarse pathway summaries of baseline expression,
which may simply not encode the determinants of radiation response; intrinsic
radiosensitivity may depend on dynamic, post-irradiation responses that a baseline profile
cannot see. And the **design is honest**: grouping by relatedness and keeping all
preprocessing inside training folds removes the two most common sources of inflated
performance.

This near-zero R² closely reproduces RadSigBench, which reported mean out-of-sample R² of
0.01 and 0.00 for seven published signatures and found them no better than random gene
sets [@oconnor2022]. **Agreement with the strongest prior negative result is a
substantive finding**, not a failure: it indicates the pipeline is measuring what it claims
to measure, and it is evidence against the more optimistic claims in the signature
literature.

## The value and uncertainty of expression-derived pathways

The pathway ranking is best read as a description of a weak fitted model. Its magnitudes
are of the same order as the whole predictive gain; its rank stability across fits is
modest (mean Kendall τ 0.225, mean top-10 Jaccard 0.391); and correlated gene sets share
or exchange importance. The appearance of HALLMARK_P53_PATHWAY at the top is biologically
*plausible*, since p53 governs the damage response, cell-cycle arrest and apoptosis, and
its dominant negative coefficient sign is consistent with higher p53-pathway activity
accompanying lower survival. But plausibility is precisely the trap: with no demonstrated
prediction gain and no negative controls, a plausible ranking is indistinguishable from a
coincidence, and the absence of DNA repair, G2M checkpoint and hypoxia from the shortlist
shows the ranking is not simply recovering textbook radiobiology. We therefore report the
ranking as capped, exploratory and hypothesis-generating, and draw no mechanistic
conclusion from it.

## How the original Moringa findings motivate follow-up work

The original study's useful contribution is a *question*, not a measurement that this
project could use: the post-irradiation proliferative response to a plant extract differed
between cell types, most clearly for the leaf extract (PEF 1.26 in V79 against 0.90 and
0.99 in the two carcinoma lines). The computational work formalises the general version of
that question on a valid endpoint, with grouping, and finds the molecular signal weak.
That does not contradict the original observation, because the endpoints differ: a 72-hour
biomass ratio measured with extract present is not intrinsic clonogenic survival. The
original observation also remains confounded, since the only apparently normal line is the
only non-human one. What the project adds is a defensible framework in which the question
can be asked properly, and an explicit statement of which experiments would be needed.

## What compound prioritisation adds, and why the candidates stay hypotheses

The compound module converts an open-ended phytochemical literature into an auditable
evidence trail: compound → documented presence in seed or leaf with a named solvent →
primary experimental association with a radiation-response process → the genes actually
measured. Its practical value is as much in what it *excludes* as in what it ranks. It
removes benzyl isothiocyanate (roots, not seed or leaf), gallic and caffeic acid (no
primary Moringa report at all), a UVB literature that is not radiation evidence,
carrier-confounded nanoparticle studies, and a retracted paper; it down-weights the free
flavonol aglycones to the weakest identification band rather than excluding them, which is
what their tentative dereplication supports; and it flags chlorogenic acid's
tumour-protection liability, which a naive "antioxidants are radioprotectors" reading would
have turned into a selling point.

The candidates remain hypotheses for specific reasons, not as a formality. No compound has
been shown to be present in the extracts that were tested, because those extracts were
never analysed. Moringin, the most Moringa-specific candidate, has no radiation study at
all. The compounds that do have radiation evidence were mostly tested at concentrations or
doses whose relevance to an extract is unknown, several at levels well above plausible
dietary exposure, and most abstracts omit the radiation dose or the concentration
altogether. An antioxidant is not therefore a radioprotector; a compound that reduces
tumour-cell viability does not therefore protect normal tissue; and a high priority score
reflects the state of the published evidence, not a predicted experimental outcome.

The connection to the machine-learning results is deliberately kept weak, because the
evidence is weak. Where the gene-set ranking is capped at tier C, the compound
prioritisation rests on external biological evidence, and any overlap between a compound's
measured genes and a ranked gene set is reported as a hypothesis. **Nothing in this report
claims that a prioritised pathway and a prioritised compound together imply an effect on
clonogenic SF2.**

## Separating supported results from plausible explanations

| Supported by the outputs | Plausible, not established |
|---|---|
| ΔMAE = 0.00383 (2.85%), nine of ten repeats favouring M2 | That expression features would improve prediction in an independent cohort |
| Out-of-sample R² near zero for all five models | That richer features or more data would raise it materially |
| M2 lower error in eight of nine well-supported tissues; worse in Pancreas | That tissue-specific differences reflect tissue-specific biology |
| Seven gene sets meet the tier-C criteria; p53 pathway ranks first | That the p53 pathway influences radiosensitivity in these lines |
| Importance rank stability is modest across fits | That a larger sample would stabilise the ranking |
| Niazimicin is confirmed in seed and leaf DCM fractions | That it was present in the original study's extracts |
| Moringin has no published ionising-radiation study | That it would behave like benzyl isothiocyanate under radiation |
| Chlorogenic acid protected HCC cells from radiation in one study | That it would protect human tumours during radiotherapy |

Table: Results supported by the saved outputs, separated from plausible explanations that are not established.

# Project implementation and challenges

**Incomplete original manuscript.** Printed page 3 and pages 7–12 are missing, removing
the extraction and culture methods, the end of the discussion, the conclusions and the
references; authors, venue and DOI are absent and no published version was found. In
Figures 1 and 2 of that manuscript the 0 Gy and 2 Gy series cannot be distinguished in the
grayscale scan. *Response:* a labelled page-by-page extraction that marks every absent item
as not stated, with no reconstruction, and no use of the figures' point values.

**Endpoint confusion as a standing risk.** The project's central scientific hazard is
quietly treating proliferation, viability and clonogenic survival as interchangeable.
*Response:* endpoints are separated in the data model, the documentation and the figure
rules; a dedicated comparison of PEF against SF2 is recorded; and a project rule forbids
placing different endpoints on one axis.

**Dataset harmonisation and licensing.** Four resources with different identifier
namespaces, release cadences and licences had to be joined, and the outcome dataset is
non-commercial (CC BY-NC 4.0). *Response:* a manifest per source with checksums and access
dates, checksum-verifying loaders, and explicit licence recording. The Hallmark GMT's
source identity remains pending the investigator's comparison with the official URL — an
open item, not a closed one.

**Cell-line identity and relatedness.** Names are ambiguous and relatedness is the most
dangerous leakage route in this design. *Response:* matching by stable identifiers only;
Cellosaurus hierarchy and origin links used to merge 241 records into 237 components;
problem flags on relatives recorded and surfaced in triage; a leakage audit of identifier,
component and split code.

**Small sample against many features.** 237 independent components support only modest
model complexity. *Response:* simple scikit-learn baselines before anything complex, a
prespecified ladder of five models, nested tuning, and a random forest confined to an
explicitly post-hoc exploratory configuration.

**Computational cost, and the deferred simulation.** The validation plan required a
coverage simulation to choose an interval method before any inference. The first pilot took
about 24–25 minutes per replicate on one core, making 9 × 500 replicates impractical
within the available time. *Response:* a static review found redundant work in the inner
tuning loop — the gene-set scorer, score scaler and validation scores were being refitted
for each of 36 grid points × 5 inner folds although they depend only on the fold rows, and
the baseline ridge was refitted per grid point although it depends only on its own
hyperparameter. The caching rewrite was designed to be bit-identical (same operations, same
order) and the original loop was retained as a reference implementation for every model it
does not apply to. Bounded multiprocessing was added (`--workers N`, spawn context,
parent-only atomic write-once checkpoints, one BLAS thread per worker), sized to the
investigator's machine (six physical cores, twelve threads, ≈31 GiB RAM). Even so, the
full study could not finish before the deadline.

**Protocol deviation, recorded before any result existed.** The deviation was written into
the decision log **before** the primary run produced a single result, which is what makes
it a deviation rather than a rationalisation: inference method set to not assessable, no
interval or p-value written, repeats fixed at ten, negative controls left at zero draws,
and the consequence that gene-set attribution can never be permitted and pathway tiers stay
capped. The deviation is reported in the results, the figures and the limitations, and the
simulation infrastructure remains in the repository ready to run.

**A presentation error found and corrected.** The version-1 within-tissue Spearman
statistic was strongly negative for the tissue-only models. Rather than report a striking
number, the code was inspected, the leave-fold-out mean artefact identified, and a
corrected version-2 table written that marks the statistic undefined where a model's
prediction is constant within a tissue. The version-1 table was kept unchanged for audit
and is not interpreted. *This is the clearest example of the write-once discipline doing
its job.*

**Missing negative controls and incomplete mechanistic validation.** Without null draws,
no gene set can exceed tier C and no attribution statement is permitted. *Response:* the
gates were enforced rather than relaxed, and the report states what cannot be claimed.

**Uncertainty in compound/extract correspondence.** The original extracts were never
chemically characterised, and the published DCM-extract literature is thin, partly
inaccessible and partly library-match only. *Response:* a three-level extraction category
recorded per compound, kept outside the score; verbatim solvent wording stored per report;
speculation in the literature (one paper's "possibly yes" for chlorogenic acid in a leaf
CH₂Cl₂ extract) explicitly excluded as evidence; and a citation error in a 2026 paper
noted, where a statement about an Indian DCM extract cites an unrelated soil-chemistry
reference.

**Abstract-level evidence extraction.** Many full texts were paywalled or failed to fetch,
so radiation doses, concentrations and even cell-line identities are missing from several
records. *Response:* every such gap is recorded as not stated with the reading depth
stored, and the gaps are listed as blocking items before publication rather than filled by
inference.

# Main deliverables and achievements

**Completed and verified.**

1. A documented, labelled extraction of the original manuscript, with every absent item
   marked and reviewed against the page images.
2. A provenance-tracked analysis dataset: 241 records, 237 independent components, 20
   tissues, with checksum-verified inputs and a recorded quality-control pass.
3. A completed primary benchmark: 250/250 model-fold tasks, five prespecified models, ten
   repeats of grouped five-fold nested cross-validation, with saved per-record out-of-fold
   predictions, metrics, per-repeat differences and a run record.
4. A completed explainability analysis: held-out permutation importance for all 50 M2 fits,
   coefficient sign consistency, gene-set score correlations and rank-stability statistics.
5. Completed pathway and cell-line triage under prespecified, enforced evidence gates:
   seven tier-C gene sets, 43 not prioritised, no tier A or B; 12/9/27 tier A/B/C cell
   lines.
6. Publication tables and captions derived only from saved outputs, with cell-line names
   taken from checksum-verified DepMap metadata.
7. A corrected within-tissue ranking analysis, with the superseded version retained for
   audit.
8. A curated, fully referenced compound-evidence base: constituent inventory with
   extraction solvent and identification strength per report, and primary radiation-biology
   evidence with model system, dose, concentration, measured genes and reported direction,
   every DOI verified against Europe PMC or Crossref and every identifier against PubChem.
9. A redesigned Seaborn figure stack with a shared visual identity, a split PNG/PDF output
   layout and provenance sidecars, with the no-title/no-footnote contract enforced by tests.
10. A prespecified compound-prioritisation protocol, its tested implementation, and the
    resulting tables: 18 compounds ranked from 21 curated constituents, 5 in tier A, with
    the liability cap and the not-assessable rule both demonstrably binding.
11. Three completed robustness analyses of the frozen cohort: the M3 random forest
    (200/200 tasks), leave-one-tissue-out (18/18) and outcome-scale sensitivity (400/400),
    each evaluated and reported as it came out, including where it weakened the primary
    reading.
12. Completed M3 explainability on held-out rows, kept separate from the primary
    explainability, which was not recomputed.
13. Eleven report figures rendered as 600 dpi PNG and vector PDF with provenance
    sidecars and a figure manifest.
14. This report, its reference list, and its figure and table manifests.

**Implemented and tested, but not executed.** These are *not* completed scientific
results, and the report does not present them as such:

| Output | Command | Status |
|---|---|---|
| Negative controls, 1000 draws of each null | `scripts/run_model.py --config configs/experiment_controls.yaml` | Infrastructure and configuration ready, cost measured at ~10–20 h; **not executed**. Tiers A and B stay closed and no gene-set p-value exists until it is |
| Coverage simulation (interval method) | `scripts/run_interval_simulation.py` | Infrastructure ready; **deferred by the recorded protocol deviation** (D04.06) |

Table: Analyses implemented and tested but not executed.

A project rule reserves all model fitting, prediction, explainability and analysis
execution to the investigator; the automated assistant prepared code, configuration,
documentation and commands only, and ran no scientific computation.

# Limitations

1. **Predictive performance is weak.** Out-of-sample R² lies between −0.018 and +0.013 for
   every model. No model in this study predicts clonogenic radiosensitivity usefully, and
   the pipeline should not be presented as a working predictor.
2. **The improvement is small and was not formally tested.** ΔMAE = 0.00383 mSF2 units
   (2.85%). No interval, no p-value and no formal superiority assessment exist, because the
   coverage simulation that would have validated an interval method was deferred.
3. **No negative controls.** Zero permuted-outcome and zero random-gene-set draws were
   completed, so the gain cannot be compared against a null reference, gene-set attribution
   is not permitted, and the stability gate is infeasible.
4. **No external validation.** Ten repeats re-split the same 237 components. Repeated
   cross-validation measures split-to-split variability, not generalisation.
5. **The improvement is not uniform, and transfer to unseen tissues is conditional.** In
   Pancreas, M2 is worse than M1 by 0.0110, nearly three times the pooled gain; in the
   leave-one-tissue-out analysis the expression-only model lost to the global mean when
   Pancreas (ΔMAE −0.0142) or Esophagus/Stomach (−0.0030) was held out.
6. **One outcome source, with aggregated labels.** CLARIFi mSF2 is a literature median
   across laboratories, dose rates and protocols, with one value per line, so per-line assay
   variability cannot be estimated; the dataset is also CC BY-NC 4.0.
7. **Small, imbalanced sample.** 237 components; eleven of 20 tissues have fewer than ten,
   and one has a single component.
8. **Pathway rankings are exploratory and modestly stable.** Mean Kendall τ 0.225, mean
   top-10 Jaccard 0.391; importance magnitudes are the size of the whole predictive gain;
   correlated sets share importance. No tier exceeds C.
9. **Cell-line discrepancies are dominated by shrinkage.** Large residuals occur mostly at
   extreme observed values and are review signals, not biological findings; measured lines
   are not independent validation samples.
10. **No compound has been shown to be present in the original extracts.** The extracts were
    never analysed; most compounds are documented in other solvents; and several DCM
    identifications are spectral-library matches from inaccessible full texts, one in a
    journal indexed in neither PubMed nor Europe PMC.
11. **The most Moringa-specific candidate has no radiation evidence.** No primary study has
    combined purified moringin or glucomoringin with ionising radiation.
12. **Compound evidence is largely abstract-level.** Radiation doses, concentrations and
    some cell-line identities are missing from several records and must be recovered from
    full texts before publication; one glucomoringin identifier remains ambiguous; one
    erratum is unread and one journal's retraction status must be re-checked.
13. **Group independence is lower than paper counts suggest.** Shared senior authors and a
    shared compound supplier link several studies; the scoring code deduplicates by research
    group, but the effective number of independent sources remains small.
14. **The within-tissue ranking statistic is not usable for the simpler models.** It is
    undefined where predictions are constant within a tissue, and biased downward elsewhere.
15. **No causal or mechanistic claim is supported anywhere.** Association, explanation of a
    fitted model, causation and experimentally demonstrated protection are four different
    things, and only the first two are in evidence here.

# Recommendations and future experimental validation

These are proposals. None has been carried out.

**Priority 1 — close the chemistry gap.** Analytically characterise the *original*
dichloromethane seed and leaf extracts by LC-MS/MS and GC-MS against authentic standards,
with niazimicin quantified by the published validated UPLC-MS/MS method as a positive
control. Until this is done, no compound-level interpretation of the original result is
possible. Report yields and concentrations as measured; do not infer them.

**Priority 2 — resolve identities.** Confirm the structures and public identifiers of
shortlisted compounds, settle the glucomoringin stereochemistry, obtain the paywalled full
texts, and recover the missing radiation doses and concentrations. Re-verify the
retraction status of the flagged journal and read the outstanding erratum.

**Priority 3 — complete the statistical validation that was deferred.** Run the coverage
simulation to choose and justify an interval method, then re-check the primary comparison
at the adopted method, and run at least 1,000 draws of each negative control
(permuted outcome, random gene sets). Only then can superiority be assessed, gene-set
attribution be permitted, or any pathway exceed tier C. The infrastructure for all of this
is in the repository.

**Priority 4 — purified compounds against whole extracts, on the right endpoint.**
Multi-dose **clonogenic survival** assays (not 72-hour biomass) with and without compound
or extract, yielding linear-quadratic parameters and a dose-modifying factor. Include
vehicle-only and cell-free interference controls, which the original study did not
describe, and independent biological repeats on separate days and passages, since the
original replicates were technical wells with dose confounded with plate.

**Priority 5 — make the normal-versus-tumour comparison interpretable.** Use
species-matched and tissue-matched normal/tumour pairs assayed identically, so that
species, tissue and malignancy are not confounded as they were when one hamster fibroblast
line was compared with two human carcinoma lines. A selectivity claim requires treated
normal **and** treated tumour measurements on the same endpoint; the best published model
of how to word such a claim is the quercetin result of Horton and colleagues
[-@horton2013], which reports normal-tissue anti-fibrotic protection with **no** effect on
fibroblast or murine tumour radioresponse.

**Priority 6 — test the prioritised pathways directly, if the validation in Priority 3
succeeds.** Perturb the implicated processes (for example p53-pathway activity) in a small
panel spanning the predicted range, and measure clonogenic survival. Treat this as
hypothesis testing of a model-derived conjecture, not confirmation.

**Priority 7 — strengthen the benchmark itself.** Seek a second, independent
radiosensitivity source for cross-assay evaluation reported as heterogeneity rather than
pooled; consider prospective prediction on unassayed lines under a panel-selection rule
written into the protocol *before* predictions are viewed, reported as a designed
validation panel and not an unbiased external cohort.

# Conclusion

This project set out to connect an unpublished *Moringa oleifera* irradiation study to a
defensible computational investigation of cellular radiosensitivity, and to use the result
to identify compounds worth testing.

**What was established.** A reproducible, provenance-tracked pipeline links public
clonogenic radiosensitivity data to baseline expression for 237 independent biological
components, with cell-line relatedness handled correctly and all preprocessing inside
training folds. Within that design, pathway-level expression features reduce the error of a
tissue-only baseline by 0.00383 mSF2 units, 2.85%, consistently in direction across nine of
ten cross-validation repeats but small, non-uniform across tissues, and unvalidated by any
formal test. Overall predictive power is weak: out-of-sample R² is near zero for every
model, closely reproducing the strongest published negative benchmark in this field. The
project also produced a curated, fully referenced evidence base on *Moringa* constituents
in which the extraction solvent is tracked explicitly, and which establishes that
niazimicin is the only constituent confirmed in a dichloromethane fraction of seed and leaf,
and that the isothiocyanate most characteristic of the plant has no published
ionising-radiation study at all.

Three further analyses of the same frozen cohort tested how robust that small advantage
is. A random forest did worse than the linear offset model; the advantage nearly vanished
on one transformed outcome scale and grew on another; and an expression-only model
transferred to an unseen tissue with the only clearly positive out-of-sample R² in the
project, but lost to the global mean when Pancreas or Esophagus/Stomach was held out. The compound module produced a shortlist of 18
candidates with 5 in tier A, in which the prespecified liability cap and the
not-assessable rule both visibly bound, and in which the compound best documented in the
actual extraction solvent carries no radiation evidence at all.

**What remains hypothetical.** Everything downstream of the prediction. The pathway
ranking is capped at an exploratory tier because no prediction gain was formally shown and
no negative controls were run. The cell-line discrepancies are review signals dominated by
shrinkage. No compound has been shown to be present in the extracts that were tested, no
compound has been shown to modify clonogenic survival in this work, and no claim of
selective radioprotection is made or supported. The candidate tiers describe the state of
the published evidence, not expected experimental outcomes.

The project's contribution is therefore methodological and evidential rather than
predictive: a transparent framework, an honest negative-leaning benchmark that agrees with
the best prior work, a correction of its own earlier artefact, an explicit record of a
deadline-driven protocol deviation, and a traceable path from the original radiobiology to
a small set of experiments that would actually settle the question. The most valuable
single output may be the mismatch the compound curation revealed — the compound present in
the right solvent has no radiation data, and the compounds with radiation data were never
found in that solvent — because it converts a diffuse phytochemical question into two
specific, feasible experiments.

\newpage

# References {.unnumbered}

::: {#refs}
:::

\newpage

# Appendices {.unnumbered}

## Appendix A — Configuration and commands {.unnumbered}

| Step | Configuration | Script |
|---|---|---|
| Preprocessing and QC | `configs/preprocessing.yaml` | `scripts/run_preprocessing.py` |
| Primary experiment | `configs/experiment.yaml` | `scripts/run_model.py` |
| Evaluation | `configs/experiment.yaml` | `scripts/evaluate_models.py` |
| Explainability | `configs/experiment.yaml` | `scripts/run_explainability.py` |
| Pathway and cell-line triage | `configs/triage.yaml` | `scripts/generate_triage.py` |
| Publication tables | `configs/publication.yaml` | `scripts/make_publication_tables.py` |
| Compound evidence and ranking | `configs/compounds.yaml` | `scripts/make_compound_tables.py` |
| Report figures | `configs/figures_report.yaml` | `scripts/make_report_figures.py` |
| Coverage simulation (deferred) | `configs/simulation.yaml` | `scripts/run_interval_simulation.py` |

Table: Configuration file and script for each step of the pipeline.

The ordered command sequence is in `reports/french_embassy/README.md`.

## Appendix B — Data provenance {.unnumbered}

Dataset manifests: `data/manifests/` (one YAML per source and release, with DOI, URL,
licence, access date, per-file SHA-256, column meanings, units, endpoint definition and
transformations). Run records: `results/models/primary_v1/run_manifest.json`,
`results/tables/primary_v1/evaluation_record.json`,
`results/triage/primary_v1/triage_manifest.json`, and the compound record written by
`scripts/make_compound_tables.py`. Each records the git commit, a dirty-tree flag,
configuration checksum, input and output checksums, package versions and UTC timestamps.

## Appendix C — Methodological detail {.unnumbered}

Protocol: `docs/protocol.md`. Architecture and naming: `docs/architecture.md`. Data rules:
`docs/data_management.md`. Figure standards: `docs/figure_standards.md`. Compound
prioritisation rules: `docs/compound_protocol.md`. Reviewer matrix and reconciliation
rules: `docs/agent_workflow.md`. Phase gates: `docs/research_roadmap.md`. Every decision,
open question and investigator ruling: `docs/decision_log.md`.

## Appendix D — Supplementary tables {.unnumbered}

| Table | File |
|---|---|
| Table 1. Dataset composition by tissue | `results/tables/primary_v1/publication_v1/table_1_dataset_composition.csv` |
| Table 2. Model comparison | `.../table_2_model_comparison.csv` |
| Table 3. Tissue-specific performance | `.../table_3_tissue_performance.csv` |
| Table S1. ΔMAE per cross-validation repeat | `.../table_s1_repeat_delta_mae.csv` |
| Table S2. Exploratory gene-set ranking | `.../publication_triage_v1/table_s2_gene_set_ranking.csv` |
| Table S3. Cell-line discrepancy review | `.../publication_triage_v1/table_s3_discrepancy_review.csv` |
| Table S4. Within-tissue Spearman (corrected) | `.../publication_v1/within_tissue_spearman_v2.csv` |
| Table C1. Constituent inventory | `results/tables/primary_v1/compounds_v1/table_c1_constituent_inventory.csv` |
| Table C2. Compound–biology evidence | `.../table_c2_biology_evidence.csv` |
| Table C3. Candidate ranking | `.../table_c3_candidate_ranking.csv` |
| Table C4. Compound–pathway gene overlap | `.../table_c4_pathway_overlap.csv` |
| Table R1. Exploratory model comparison including M3 | `results/tables/exploratory_m3_v1/model_metrics.csv` |
| Table R2. Leave-one-tissue-out performance by held-out tissue | `results/tables/loto_v1/held_out_tissue.csv` |
| Table R3. Outcome-scale sensitivity (neglog and logit) | `results/tables/scales_v1/comparisons.csv` |

Table: Supplementary result tables and the files that hold them.

Machine-readable manifests in this folder: `table_manifest.csv` (tracked, with a
per-table generation status) and `figure_manifest.csv` (written by
`scripts/make_report_figures.py`, mapping each figure number to the file actually rendered
and to its full caption).

## Appendix E — Candidate evidence records {.unnumbered}

The complete curated records, with every citation, DOI, verification route, reading depth,
extraction solvent, identification method, model system, radiation dose, concentration,
measured genes and reported direction, are in `data/compounds/moringa_constituents.yaml`
and `data/compounds/compound_biology_evidence.yaml`. The curation audit trail — searches
run, exclusions applied, identifier problems found and resolved, and the unresolved gaps
that must be closed before publication — is in `docs/compound_evidence_curation.md`.

## Appendix F — Supplementary figures {.unnumbered}

![**Figure S1.** Stability of each cell line's out-of-fold prediction across the ten cross-validation repeats, by model: the distribution over records of the standard deviation of the prediction. Violins show the kernel density over all 241 records with the quartiles marked; the quantity is split-to-split variability of the prediction and is not a prediction interval or a confidence interval, and it widens with the number of repeats. The expression models vary more between splits than the tissue-only models, whose prediction is a shrunken tissue mean.](../../figures/png/fig_s01_prediction_variability.png){#fig:s01 width=100%}

![**Figure S2.** Spearman correlation between the Hallmark gene-set scores of the tier-C sets and of every set flagged as sharing signal with them (absolute correlation at least 0.80), computed over the eligible cell lines from the expression features alone. Rows and columns follow the triage rank order; no clustering is applied, so no grouping here should be read as a biological relationship. Correlated scores can share or exchange permutation importance, so neighbouring sets in Figure 6 are not independent findings.](../../figures/png/fig_s02_gene_set_correlation.png){#fig:s02 width=100%}

## Appendix G — Reproducibility information {.unnumbered}

Environment: `environment.yml` (conda, `explainable-radiosensitivity-ml`; Python 3.11).
Versions are not yet pinned and no lockfile exists; pinning awaits the environment review.
Hardware used for the primary run: six physical CPU cores, twelve logical threads, ≈31 GiB
RAM, with one BLAS thread per worker and bounded multiprocessing. Tests: `tests/`, run with
`pytest`; tests that would fit a model are marked `model_fit` and are excluded from routine
runs. Figures and result folders are write-once; regeneration requires an explicit version
bump or an explicit overwrite flag.
