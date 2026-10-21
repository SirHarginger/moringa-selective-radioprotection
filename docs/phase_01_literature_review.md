# Phase 01 literature review

**Project:** Explainable Radiosensitivity ML. **Phase:** phase_01. **Search and verification date:** 2026-10-21.
**Prepared by:** literature-reviewer subagent (two passes: Part A = ML, radiogenomics, cross-dataset, tissue, explainability; Part B = datasets, normal cells, plant extracts). Assembled by Claude Code. **Skill applied:** `literature-evidence-map`.

> **Verification standard (read first).**
> - Every DOI and PMID was checked against Europe PMC REST metadata (`EPMC`) and/or the Crossref API (`CR`).
> - Quantitative findings were read from the full text (`FT`, via PMC or Europe PMC `fullTextXML`) or from the abstract only (`ABS`). They were read through a web-fetch tool that summarises pages, so **every number must be checked against the PDF before it is cited in a manuscript.**
> - "Not extracted" means the value was not read. Items that could not be verified are listed under "Unverified leads" and must not be cited.
> - No code was run and no data were analysed.

Contents: Part A (§A1–A8), Part B (§B1 onward), consolidated novelty answers (§C).

---

# Part A: ML, radiogenomics, cross-dataset validation, tissue confounding, explanation stability

## A1. Framing (PECO)

| Element | Definition |
|---|---|
| **P**opulation | Human cancer cell lines, pan-cancer or single tissue, with baseline (unirradiated) molecular profiles. Normal fibroblast strains noted where relevant |
| **E**xposure / predictor | Basal molecular features, mainly mRNA expression; also CNV, mutation and protein, used in statistical or ML predictors of radiation response |
| **C**omparator | Simple baselines (mean, single gene, tissue-only), published signatures (e.g. RSI), alternative datasets and assays |
| **O**utcomes | (i) Radiation endpoint, with the assay recorded: clonogenic SF2/mSF2, high-throughput (HT) integral survival/AUC (CellTiter-Glo, 9 days), other. (ii) Predictive performance within and across independent datasets. (iii) Tissue-of-origin contribution. (iv) Explanation stability |

**Questions:**
- **(a)** Have gene-expression radiosensitivity models been trained and evaluated across independent datasets?
- **(b)** Have tissue-only baselines been used to show what molecular features add beyond tissue?
- **(c)** Has the stability of SHAP or similar explanations been assessed for radiosensitivity models?

**Inclusion:** primary studies (English, any year) that predict or associate in-vitro radiation response from molecular features; studies that directly inform cross-dataset validation, tissue confounding (pharmacogenomic studies allowed, labelled as such) or explanation stability; dataset source papers.

**Exclusion:** radiomics and imaging; clinical-only toxicity models; acquired-resistance derivative models (except as context); conference abstracts.

## A2. Search log

Abbreviations: WS = general web search; EPMC = Europe PMC REST `search?query=…&format=json&resultType=core`; CR = `api.crossref.org/works/<doi>`; FT = PMC page or `europepmc/webservices/rest/<PMCID>/fullTextXML`.

| # | Database | Query (verbatim) | Purpose | Retained |
|---|---|---|---|---|
| 1 | WS (extended) | `machine learning prediction cellular radiosensitivity SF2 cancer cell lines gene expression CCLE` | Topics 1–3 | Zeng 2022; Oike 2025; Kim & Chung 2022; Wang 2016; Tobiasz 2023 |
| 2 | WS | `Manem radiogenomic RadioGx modeling cellular response large-scale radiogenomic databases Cancer Research` | Topics 2, 7 | Manem 2019 |
| 3 | WS (extended) | `deep learning radiosensitivity prediction Yard 2016 high-throughput radiation profiling cell lines AUC integral survival model` | Topics 1, 6 | Komatsu 2019; one lead |
| 4 | WS | `Yard Abazeed "genetic basis for the variation in the vulnerability of cancer to DNA damage" Nature Communications 2016` | Dataset source | Yard 2016 |
| 5 | WS (extended) | `radiosensitivity gene signature validation across independent cell line datasets NCI-60 and Yard CCLE radiation profiling comparison` | Topic 6 | Hall 2014; Kim 2012; Kolnohuz 2024; Manem 2021 |
| 6 | WS (extended) | `SHAP explainable machine learning radiosensitivity cancer cell lines radiation response interpretability` | Topic 8 | None relevant (clinical radiomics only) |
| 7 | WS (extended) | `CLARIFi mSF2 machine learning prediction radiosensitivity 2025 2026` | Novelty | No ML on CLARIFi found |
| 8 | WS (extended) | `radiation response prediction cancer cell lines DepMap transcriptome machine learning leave-one-tissue-out interpretable 2024` | Topics 6–8 | Yu 2025 (arXiv) |
| 9 | WS | `Feasibility study deep learning radiosensitivity prediction NCI-60 gene expression Nuclear Engineering and Technology authors` | Topic 1 | Kim & Chung 2022; Zhang 2014 |
| 10 | WS (extended) | `"SHAP" "surviving fraction" OR "SF2" cell lines radiosensitivity gene expression model feature importance` | Topic 8 | Peng 2025 (arXiv) |
| 11 | WS | `Janizek ensembles of explainable machine-learning models synergistic drug responses Nature Biomedical Engineering SHAP correlated features` | Topic 8 (adjacent) | Janizek 2023 |
| 12 | WS | `Xia cross-study analysis of drug response prediction in cancer cell lines Briefings in Bioinformatics generalization` | Topic 6 (pharmacogenomic) | Xia 2022 |
| 13 | WS | `Lloyd "between-tissue differences" pan-cancer predictions of drug sensitivity PLoS Computational Biology` | Topic 7 | Lloyd 2021 |
| 14 | WS | `Lewis Kemp integration of machine learning and genome-scale metabolic modeling multi-omics biomarkers radiation resistance Nature Communications 2021` | Topic 1 (context) | Lewis 2021 (peripheral) |
| 15 | WS (extended) | `stability of SHAP feature attributions gene expression models bootstrap resampling reproducibility explanations omics` | Topic 8 | Haury 2011; leads only |
| 16 | WS (extended) | `radiosensitivity cell lines "tissue of origin" baseline model gene expression adds predictive value beyond cancer type SF2 integral survival` | Topic 7 | Kamath 2017 |
| 17 | WS | `radiosensitivity index RSI evaluated Cleveland Yard cell line integral survival CCLE correlation validation` | Topic 6 | No direct RSI-vs-Yard study found |
| 18 | WS (extended) | `pan-cancer cell line radiation sensitivity prediction model external validation NCI-60 independent cohort 2023 2024 2025 deep learning gene expression Yard` | Topic 6 | Yang 2024 (RISE) |
| 19 | WS | `"Exploring Strategies for Personalized Radiation Therapy" arXiv Part I Part II` | Peng series | Parts I–II are imaging; excluded |
| E1–E12 | EPMC | Author/title/DOI queries, e.g. `AUTH:"Torres-Roca" AND TITLE:"radiation sensitivity" AND PUB_YEAR:2005`; `DOI:10.1038/ncomms11428`; `AUTH:"Kim HS" AND TITLE:"radiosensitivity signature" AND TITLE:"NCI-60"`; `AUTH:"Geeleher P" AND TITLE:"general levels of drug sensitivity"`; plus DOI batches | Identifier verification | See tables |
| C1–C3 | CR | `10.1016/j.net.2021.10.020`, `10.1158/0008-5472.CAN-05-0656`, `10.1158/0008-5472.CAN-07-2120` | DOI verification | All confirmed |

**Not searched in Part A:** PubMed web interface (Europe PMC used instead), Scopus, Web of Science, Embase, Google Scholar forward-citation chasing, bioRxiv/medRxiv full text.

## A3. Extraction table: radiation-specific primary studies

Assay codes: **CLON** = clonogenic; **HT-CTG** = high-throughput 9-day CellTiter-Glo (ATP) viability on the Yard/Abazeed platform. Verification codes as above.

| # | Citation | DOI / PMID (verif.) | Objective | Dataset and samples | Endpoint (assay) | Methods | Validation | Principal findings | Limitations | Relevance; already done? |
|---|---|---|---|---|---|---|---|---|---|---|
| R1 | Torres-Roca JF, Eschrich S, Zhao H, et al. Prediction of radiation sensitivity using a gene expression classifier. *Cancer Res* 2005;65(16):7169–7176 | 10.1158/0008-5472.CAN-05-0656 / 16103067 (EPMC, CR; ABS) | Expression classifier for SF2 | NCI-60; classifier tested on 35 lines | SF2 (assay source not stated in abstract) | SAM + multivariate linear regression | Not extracted | SF2 correctly predicted in 22/35 (P = 0.0002, abstract). RbAp48 overexpression radiosensitised 3 lines | Small n; full text not read | Foundation of RSI; single dataset |
| R2 | Eschrich S, Zhang H, Zhao H, et al. Systems biology modeling of the radiation sensitivity network… *Int J Radiat Oncol Biol Phys* 2009;75(2):497–505 | 10.1016/j.ijrobp.2009.05.056 / 19735874; PMC2762403 (EPMC; ABS) | Network model of SF2 | 48 cancer lines | SF2 | Linear regression: expression + ras + tissue of origin + p53; 10-hub network | c-Jun knockdown in 8 lines | Abstract: **ras and tissue of origin were the dominant variables**; p53 was not | In-sample; full text not read | **(b):** tissue modelled as a covariate; no out-of-sample tissue-only baseline |
| R3 | Eschrich SA, Pramana J, Zhang H, et al. A gene expression model of intrinsic tumor radiosensitivity… *Int J Radiat Oncol Biol Phys* 2009;75(2):489–496 | 10.1016/j.ijrobp.2009.06.014 / 19735873; PMC3038688 (EPMC; ABS) | RSI clinical validation | Same 48 lines; 118 patients | SF2 (lines); clinical response | 10-gene rank-based linear model (RSI) | Clinical cohorts | e.g. rectal RSI 0.32 vs 0.46 (p = 0.03) (abstract) | Small cohorts | RSI origin; no cross-cell-line-dataset test |
| R4 | Kamath VP, Torres-Roca JF, Eschrich SA. Integrating biological covariates into gene expression-based predictors of radiation sensitivity. *Int J Genomics* 2017;2017:6576840 | 10.1155/2017/6576840 / 28280724; PMC5320380 (EPMC; FT) | Do tissue, RAS and p53 covariates improve expression models? | 48 lines (mostly NCI-60) | SF2 (prior reports) | Expression-only vs additive vs interaction linear models; random-variable controls | LOOCV; permutation; **in-sample adjusted R²** | Additive covariate gains were similar to those from random variables. Interaction terms raised adjusted R² (e.g. +0.272, tissue × RAS). Covariate-only R² not reported | In-sample; many terms for n = 48; competing interests declared | **Closest radiation study to (b)**, but no out-of-sample tissue-only baseline |
| R5 | Amundson SA, Do KT, Vinikoor LC, et al. Integrating global gene expression and radiation survival parameters across the 60 cell lines of the NCI Anticancer Drug Screen. *Cancer Res* 2008;68(2):415–424 | 10.1158/0008-5472.CAN-07-2120 / 18199535 (EPMC, CR; ABS) | Expression vs radiation survival | NCI-60 + 3 lines | Clonogenic survival after 2 and 8 Gy γ; apoptosis | Differential expression | Not extracted | 22 genes associated with low survival after 2 Gy; basal expression discriminated better than induced expression (abstract) | Full text not read | Source of NCI-60 SF2 |
| R6 | Kim HS, Kim SC, Kim SJ, et al. Identification of a radiosensitivity signature using integrative metaanalysis of published microarray data for NCI-60 cancer cells. *BMC Genomics* 2012;13:348 | 10.1186/1471-2164-13-348 / 22846430; PMC3472294 (EPMC; ABS) | Cross-platform signature | NCI-60; 4 microarray platforms | SF2 (CLON) | Linear regression, SAM, global test | **No independent validation** | 31-gene signature common to all 4 platforms | Single panel | Cross-platform, not cross-dataset |
| R7 | Hall JS, Iype R, Senra J, et al. Investigation of radiosensitivity gene signatures in cancer cell lines. *PLoS One* 2014;9(1):e86329 | 10.1371/journal.pone.0086329 / 24466029; PMC3899227 (EPMC; FT) | Test published signatures across cohorts | Cervix 16 lines (14 with SF2), HNSCC 11, NCI-60 | **CLON** SF2 | Rank Product, LIMMA, PCA of signatures | **Cross-cohort** | 2/138 SF2 genes shared between cervix and HNSCC (abstract; Results say 4/138, not reconciled). RSI did not separate NCI-60, cervix (p = 0.74) or HNSCC (p = 0.32) | Very small n; median split | **Early answer to (a):** poor cross-dataset transfer |
| R8 | Zhang C, Girard L, Das A, et al. Nonlinear quantitative radiation sensitivity prediction model based on NCI-60 cancer cell lines. *Sci World J* 2014;2014:903602 | 10.1155/2014/903602 / 25032244; PMC4083270 (EPMC; FT) | Nonlinear SF2 model | NCI-60 (59; GSE32474) | SF2 (published) | SAM (129 genes) → PLS → SVR | 10 × 3-fold CV | RMSE 0.011; 54/59 within ±10% | **Probable leakage** (reviewer inference): feature selection appears to use all 59 lines before CV | Example of an optimistic within-panel estimate |
| R9 | Kim E, Chung Y. Feasibility study of deep learning based radiosensitivity prediction model of National Cancer Institute-60 cell lines using gene expression. *Nucl Eng Technol* 2022;54(4):1439–1448 | 10.1016/j.net.2021.10.020 / no PMID (CR; ABS) | CNN on NCI-60 | 174 replicate arrays from NCI-60 | CLON SF2 (published) | CNN | 6-fold CV + LOOCV | 172/174 "correct" | **Probable replicate leakage** (reviewer interpretation): replicate arrays in sample-level folds | Cautionary example |
| R10 | Wang WA, Lai LC, Tsai MH, Lu TP, Chuang EY. Development of a prediction model for radiosensitivity using the expression values of genes and long non-coding RNAs. *Oncotarget* 2016;7(18):26739–26750 | 10.18632/oncotarget.8496 / 27050376; PMC5042011 (EPMC; ABS) | Gene + lncRNA predictor | GSE26835; NCI-60 | NCI-60 radiation parameters | ANOVA, network, GA, SVM | Clinical survival cohorts | 41 features | Clinical, not cell-line, validation | Low |
| R11 | Yard BD, Adams DJ, Chie EK, et al. A genetic basis for the variation in the vulnerability of cancer to DNA damage. *Nat Commun* 2016;7:11428 | 10.1038/ncomms11428 / 27109210; PMC4848553 (EPMC; FT) | Pan-cancer HT radiation profiling | 533 lines, 26 cancer types | **HT-CTG** integral survival (384-well, ¹³⁷Cs, 1–10 Gy, 9 days; trapezoid AUC on log₂ dose, scaled 0–7) | Information-coefficient associations; **no predictive model** | — | Correlation with clonogenic in 15 lines: r = 0.85 (single), 0.89 (duplicates). About 5–7-fold variation within lineages | Associations only | Dataset source; HT ≠ clonogenic |
| R12 | Abazeed ME, Adams DJ, Hurov KE, et al. Integrative radiogenomic profiling of squamous cell lung cancer. *Cancer Res* 2013;73(20):6289–6298 | 10.1158/0008-5472.CAN-13-1616 / 23980093; PMC3856255 (EPMC; ABS) | Develop the HT platform | LUSC lines (n not extracted) | HT platform validated against clonogenic | ssGSEA | Not extracted | NFE2L2 activation linked to resistance | Abstract only | Origin of the HT-CTG assay |
| R13 | Manem VSK, Lambie M, Smirnov P, et al. Modeling cellular response in large-scale radiogenomic databases to advance precision radiotherapy. *Cancer Res* 2019;79(24):6227–6237 | 10.1158/0008-5472.CAN-19-0179 / PMID 31558563 (methodologist, EPMC); PMC8128135 (FT) | RadioGx; assay reliability; tissue-specific pathways | Yard 533 → 498 with LQ fits; CCLE expression | HT-CTG; AUC and SF2–SF8 from LQ fits | LQ modelling, GSEA | Associations only | AUC vs clonogenic r ≥ 0.8 (n = 15); AUC–SF2 ρ = 0.92. **No pathway significant across all tissues** | Concordance on n = 11–15; internal count inconsistency (2,281 vs 281) | Supports tissue-specific biology; not a predictive benchmark |
| R14 | Manem VSK. Development and validation of genomic predictors of radiation sensitivity using preclinical data. *BMC Cancer* 2021;21(1):937 | 10.1186/s12885-021-08652-4 / 34416855; PMC8377977 (EPMC; FT) | Compare ML predictors of SF2 | Train: Yard 511 lines (23 tissues; CCLE RNA-seq). Test: NCI-60 (60) | SF2: LQ-derived from HT-CTG (train) vs NCI-60 (test) → **cross-assay** | Single gene, rank ensemble, mRMR, elastic net | 10 × 10-fold CV; **Yard → NCI-60** | Best external C-index 0.59 | **No tissue covariate, grouped CV or tissue baseline; overlap between the training and test lines not checked** | **(a) partially done** (Yard → NCI-60) |
| R15 | Kolnohuz A, Ebrahimpour L, Yolchuyeva S, Manem VSK. Gene expression signature predicts radiation sensitivity in cell lines using the integral of dose–response curve. *BMC Cancer* 2024;24:2 | 10.1186/s12885-023-11634-3 / 38166789; PMC10763485 (EPMC; FT) | AUC-based predictor | Yard 511 → NCI-60 60; features from 35 published signatures | LQ AUC | Correlation ranking + linear regression (22 genes) | 10 × 10-fold CV; **Yard → NCI-60** | CV C-index 0.65; NCI-60 C-index 0.61. Pathways differ by endpoint (AUC vs SF2) | No tissue in model; no stability analysis; no overlap check | **(a) done** for Yard → NCI-60; interpretation depends on endpoint |
| R16 | Zeng Z, Luo M, Li Y, et al. Prediction of radiosensitivity and radiocurability using a novel supervised artificial neural network. *BMC Cancer* 2022;22:1243 | 10.1186/s12885-022-10339-3 / 36451111; PMC9713966 (FT, partial) | ANN-SCGP for SF2 | 82 lines (CCLE/GDSC); 60-line "He et al." set; TCGA | SF2 "from previous laboratory experiments" | ANN vs LM, LASSO, EN, SVM, RF, PLS, RSI | 5-fold CV | Test RMSE: ANN-SCGP 0.1587, RSI 0.4167 | No mean or tissue baseline; possible feature selection outside CV; no tissue grouping | Within-dataset; interpretability without stability |
| R17 | Oike T, Kambe R, Darwis NDM, et al. Establishment of cancer cell radiosensitivity database linked to multi-layer omics data. *Cancer Sci* 2025;116(3):690–697 | 10.1111/cas.16334 / 39668120; PMC11875790 (FT) | Literature-mined clonogenic SF2 database (CLARIFi) | 285 lines, 28 cancer types (263 solid, 22 blood); 926 studies (methodologist reading) | **CLON** SF2 → mSF2 | Correlations only | vs in-house clonogenic (n = 23); **vs Yard integral survival** | vs in-house r = 0.50 (≥3 papers: 0.60). **vs Yard r = 0.28 (n = 187); ≥3 papers r = 0.35 (n = 84).** NFE2L2 mRNA r = 0.086 (not significant) | No ML; between-study variability not modelled; values per line not reported | **The CLARIFi–Yard label comparison is already published.** No ML on CLARIFi found |
| R18 | Komatsu S, Oike T, Komatsu Y, et al. Deep learning-assisted literature mining for in vitro radiosensitivity data. *Radiother Oncol* 2019;139:87–93 | 10.1016/j.radonc.2019.07.003 / 31431384 (EPMC; ABS) | Pipeline behind CLARIFi | 1,805 + 222 publications | SF2 extraction (CLON) | CNN classifiers; graph reader | vs radiation oncologists | Sensitivity 91.2 ± 3.4% | — | Provenance of CLARIFi values |
| R19 | Speers C, Zhao S, Liu M, et al. Development and validation of a novel radiosensitivity signature in human breast cancer. *Clin Cancer Res* 2015;21(16):3667–3677 | 10.1158/1078-0432.CCR-14-2898 / 25904749 (EPMC; ABS) | Breast radiosensitivity signature | Breast lines (n not extracted) | **CLON** SF2 | Spearman + random forest | Clinical cohorts | 147 → 51 genes | Single tissue | Tissue-specific signature |
| R20 | Scott JG, Berglund A, Schell MJ, et al. A genome-based model for adjusting radiotherapy dose (GARD). *Lancet Oncol* 2017;18(2):202–211 | 10.1016/S1470-2045(16)30648-9 / 27993569; PMC7771305 (EPMC; ABS) | GARD = RSI + LQ model | 8,271 tumours; 538 patients | Clinical outcomes | Cox models | Clinical | — | Clinical | Context only |
| R21 | Tobiasz J, Al-Harbi N, Bin Judia S, et al. Multivariate piecewise linear regression model to predict radiosensitivity using the association with the genome-wide copy number variation. *Front Oncol* 2023;13:1154222 | 10.3389/fonc.2023.1154222 / 37849808; PMC10577171 (EPMC; FT) | CNV → SF2 | **129 normal fibroblast strains** | CLON SF2 | Forward selection; piecewise regression | Single 116/13 split | — | Tiny validation set | Normal-cell analogue |
| R22 | Yang Q, Zhou X, Fang J, et al. Development and validation of a radiosensitivity model to evaluate radiotherapy benefits in pan-cancer (RISE). *Cancer Sci* 2024;115(6):1820–1833 | 10.1111/cas.16168 / 38571294; PMC11145160 (FT) | 9-gene RISE | 5 parental-vs-resistant GEO datasets | Colony formation (acquired resistance) | LR + LASSO | Cross-dataset | — | **Acquired resistance ≠ intrinsic SF2** | Low |

**Preprints** (existence verified on the arXiv abstract page only; not peer reviewed):
- Peng H, Zhang Y, Jiang S, Timmerman R, Minna J. *Exploring Strategies for Personalized Radiation Therapy: Part III … Meta Learning.* arXiv:2508.08030 (2025). SF2 from expression vs RSI; design not given in the abstract.
- Yu Y, Xu G, Jiang S, et al. *Integrated transcriptomic-proteomic biomarker identification for radiation response prediction in NSCLC cell lines.* arXiv:2511.22735 (2025). 73 RNA-seq lines; LASSO + SVR; 10 × 5-fold CV. SF2 assay not stated in the abstract.

## A4. Adjacent literature (pharmacogenomic or methodological; not radiation-specific)

| # | Citation | DOI / PMID (verif.) | Key point | Relevance |
|---|---|---|---|---|
| P1 | Lloyd JP, Soellner MB, Merajver SD, Li JZ. Impact of between-tissue differences on pan-cancer predictions of drug sensitivity. *PLoS Comput Biol* 2021;17(2):e1008720 | 10.1371/journal.pcbi.1008720 / 33630864; PMC7906305 (EPMC; FT) | MEK inhibitors. A tissue-only regularised baseline was worse than the full model but similar to tissue-standardised predictions. Within-tissue prediction succeeded in about half of the tissues. Tissue-standardised ρ is 0.26–0.46 in the Results vs 0.30–0.51 in the abstract (source inconsistency) | **Methodological template for (b)** (drug, not radiation) |
| P2 | Jaeger S, Duran-Frigola M, Aloy P. Drug sensitivity in cancer cell lines is not tissue-specific. *Mol Cancer* 2015;14:40 | 10.1186/s12943-015-0312-6 / 25881072 (EPMC; ABS) | Cancer-specific drugs were not more effective in lines of the matching tissue | Counterpoint on tissue effects |
| P3 | Geeleher P, Cox NJ, Huang RS. Cancer biomarker discovery is improved by accounting for variability in general levels of drug sensitivity in pre-clinical models. *Genome Biol* 2016;17:190 | 10.1186/s13059-016-1050-9 / 27654937 (EPMC; ABS) | A per-line "general sensitivity" confounder | Suggests a proliferation/fitness baseline (hypothesis for radiation) |
| P4 | Haibe-Kains B, El-Hachem N, Birkbak NJ, et al. Inconsistency in large pharmacogenomic studies. *Nature* 2013;504(7480):389–393 | 10.1038/nature12831 / 24284626 (EPMC; ABS) | Genomic data concordant across CCLE and GDSC; drug responses discordant | Precedent for response-label inconsistency |
| P5 | Safikhani Z, Smirnov P, Freeman M, et al. Revisiting inconsistency in large pharmacogenomic studies. *F1000Res* 2016;5:2333 | 10.12688/f1000research.9611.3 / 28928933 (EPMC; ABS) | Partial consistency | As P4 |
| P6 | Xia F, Allen J, Balaprakash P, et al. A cross-study analysis of drug response prediction in cancer cell lines. *Brief Bioinform* 2022;23(1):bbab356 | 10.1093/bib/bbab356 / 34524425 (EPMC; ABS) | Within-study validation overstates generalisation across studies | **Design template for cross-dataset evaluation** |
| P7 | Janizek JD, Dincer AB, Celik S, et al. Uncovering expression signatures of synergistic drug responses via ensembles of explainable machine-learning models. *Nat Biomed Eng* 2023;7(6):811–829 | 10.1038/s41551-023-01034-0 / 37127711 (EPMC; ABS) | Correlated transcriptomes make naive attributions unreliable; ensembles of explainable models help | **Closest evidence for (c)** (drug synergy) |
| P8 | Haury AC, Gestraud P, Vert JP. The influence of feature selection methods on accuracy, stability and interpretability of molecular signatures. *PLoS One* 2011;6(12):e28210 | 10.1371/journal.pone.0028210 / 22205940 (EPMC; ABS) | The choice of feature-selection method affects signature stability | Stability metrics for (c) |
| P9 | Ein-Dor L, Zuk O, Domany E. Thousands of samples are needed to generate a robust gene list for predicting outcome in cancer. *PNAS* 2006;103(15):5923–5928 | 10.1073/pnas.0601231103 / 16585533 (EPMC; ABS) | Gene lists are unstable at small n | Expect unstable attributions (hypothesis) |
| P10 | Rydzewski NR, Helzer KT, Bootsma M, et al. Machine learning & molecular radiation tumor biomarkers. *Semin Radiat Oncol* 2023;33(3):243–251 | 10.1016/j.semradonc.2023.03.002 / 37331779 (FT; review) | Does not discuss cross-dataset validation or SHAP stability | Secondary confirmation of the gaps |
| P11 | Lewis JE, Kemp ML. Integration of machine learning and genome-scale metabolic modeling identifies multi-omics biomarkers for radiation resistance. *Nat Commun* 2021;12:2700 | 10.1038/s41467-021-22989-1 / 33976213 (EPMC; ABS) | Patient-level labels | Peripheral |

Methods references verified by the statistical-reviewer and ml-methodologist (Europe PMC or Crossref, 2026-10-21):
- Varma & Simon, *BMC Bioinformatics* 2006;7:91 (10.1186/1471-2105-7-91; PMID 16504092);
- Bates, Hastie & Tibshirani, *JASA* 119:1434–1445 (10.1080/01621459.2023.2197686);
- Strobl et al., *BMC Bioinformatics* 2007;8:25 (10.1186/1471-2105-8-25);
- Riley et al., *BMJ* 2020;368:m441 (10.1136/bmj.m441; PMID 32188600);
- Van Calster et al., *BMC Med* 2019;17:230 (10.1186/s12916-019-1466-7; PMID 31842878);
- Collins et al. (TRIPOD+AI), *BMJ* 2024;385:e078378 (10.1136/bmj-2023-078378; PMID 38626948);
- Nosek et al., *PNAS* 2018;115:2600–2606 (10.1073/pnas.1708274114; PMID 29531091);
- Gelman & Loken, *Am Sci* 2014;102:460 (10.1511/2014.111.460; Crossref only);
- Ioannidis, *PLoS Med* 2005;2:e124 (10.1371/journal.pmed.0020124; PMID 16060722);
- Franken et al., *Nat Protoc* 2006;1:2315–2319 (10.1038/nprot.2006.339; PMID 17406473);
- Bairoch (Cellosaurus), *J Biomol Tech* 2018;29:25–38 (10.7171/jbt.18-2902-002; PMID 29805321);
- Capes-Davis et al., *Int J Cancer* 2010;127:1–8 (10.1002/ijc.25242; PMID 20143388).

Also read by the ml-methodologist, identifier not separately verified: Matsui et al. 2019, *IJMS* (PMC6747107). 620 published clonogenic experiments on 8 common lines; inter-study coefficient of variation of SF2 below 30% for those lines.

## A5. Answers to questions (a)–(c)

**(a) Cross-dataset training and evaluation: partly done.**
- Manem 2021 (R14) and Kolnohuz 2024 (R15) trained on Yard (HT-CTG, LQ-derived SF2 or AUC) and tested on NCI-60, with external C-index about 0.59–0.61.
- Hall 2014 (R7) showed that published signatures transfer poorly across clonogenic cohorts.
- Oike 2025 (R17) compared CLARIFi and Yard **labels** (r = 0.28, n = 187), not models.
- **Not found:** any model trained or tested on CLARIFi; any CLARIFi–Yard–NCI-60 three-way design; any explicit check of cell-line overlap between training and test panels; any design that separates the dataset shift from the assay shift.

**(b) Tissue-only baselines: not found for radiation.**
- Tissue was entered as an in-sample covariate (R2, R4).
- No radiation study compares out-of-sample molecular models with a tissue-only baseline or uses leave-one-tissue-out validation.
- The drug-response analogue exists (Lloyd 2021, P1).

**(c) Explanation stability: not found for radiation.**
- Indirect evidence suggests instability: gene lists barely overlap across tissues (R7); pathways depend on the endpoint (R13, R15); no pathway is shared across all tissues (R13).
- Adjacent methods: P7–P9.

## A6. Novelty matrix (Part A)

| Candidate contribution | Prior art | Status |
|---|---|---|
| Expression → SF2 model within one dataset | R1, R6, R8, R9, R14, R15, R16 | **Done** (several with probable leakage) |
| Train on Yard (HT) → test on NCI-60 | R14, R15 | **Done** |
| CLARIFi mSF2 vs Yard label correlation | R17 | **Done** (r = 0.28) |
| Train or test models on CLARIFi clonogenic mSF2 | None found | **Open** |
| Cross-assay model transfer (HT-CTG → clonogenic) | R14, R15 (Yard → NCI-60, no overlap check, no tissue baseline) | **Done** |
| *Overlap-controlled* cross-assay transfer (clonogenic mSF2 ↔ HT-CTG), reported as endpoint heterogeneity | Label correlation only (R11, R13, R17) | **Open** (corrected 2026-10-21 after research-director review D6) |
| Cell-line identity overlap audit before cross-dataset testing | None found | **Open** (methodological) |
| Out-of-sample tissue-only baseline; leave-one-tissue-out for radiation | In-sample covariates only (R2, R4); drug analogue (P1) | **Open for radiation** |
| Attribution stability across resamples, models and datasets | None for radiation; adjacent P7–P9 | **Open** |

## A7. Unverified leads (do not cite)

1. Kim E, Chung Y. "Comparison and optimization of deep learning-based radiosensitivity prediction models…" *Nucl Eng Technol* 2022 (search snippet only; DOI and PMID not retrieved).
2. "MGPLS" deep regression model for SF2 (mentioned in a search summary only).
3. Piening 2009; the Tewari signature (cited in Hall 2014; not retrieved).
4. Scott JG et al. 2021 pooled GARD analysis (not searched).
5. The "He et al." 60-line SF2 dataset used by R16 (identity unknown).
6. Full methods of the arXiv preprints 2508.08030 and 2511.22735 (not read).
7. SHAP-stability method leads (RoSHAP arXiv:2605.15154; a bootstrap feature-importance paper DOI 10.3390/appliedmath6070106; the "disagreement problem" literature; Nogueira et al. on feature-selection stability) — not read or verified.
8. DOI 10.3389/frai.2026.1807677 (proton/carbon survival model): not read; probably out of scope.
9. Details not extracted: n for R12 and R19; full methods of R1.

## A8. Gaps carried to phase_02

1. Decide in advance that Yard is a separate, heterogeneous evaluation endpoint and is never pooled with mSF2.
2. The CLARIFi–Yard–NCI-60 overlap by DepMap ID or Cellosaurus has never been reported. It is a pre-split audit (scripted for the investigator).
3. Adopt the Lloyd 2021 design for radiation: a tissue-only model, tissue-standardised performance and within-tissue ρ.
4. The performance figures of R8, R9 and possibly R16 should not be used as benchmarks, because of probable leakage (to be confirmed from their full texts).
5. Pre-specify explanation-stability metrics.
6. Not yet done: PubMed, Scopus and Web of Science searches; forward citations of R14, R15 and R17; bioRxiv.

---

# Part B: datasets, normal-cell responses, plant extracts

Labels: [V-EPMC] Europe PMC record checked; [V-CR] Crossref checked; [V-GEO] NCBI E-utilities checked; [FT] read in full text; [ABS] abstract only; [I] reviewer interpretation; [H] hypothesis.

## B1. PECO and questions

- **P:** human cancer cell lines with radiation-response data (Yard, CLARIFi, NCI-60); normal human fibroblasts and epithelial cells; plant-extract-treated models (context only).
- **E:** basal molecular profiles; for topic 10, plant extracts given with ionising radiation.
- **C:** tissue-of-origin baselines; other assays and datasets.
- **O:** clonogenic SF2/mSF2; ATP integral survival; LQ-derived AUC, SF2, α and β; normal-tissue toxicity.

Questions:
- **Q4:** What exactly does Yard 2016 measure, and who reused it?
- **Q5:** How was CLARIFi built, and who has used it?
- **Q9:** What is known about normal-cell radiosensitivity, and what is GSE184119?
- **Q10:** What is the Moringa–radiation evidence, and was the original manuscript published?
- **QN:** What NCI-60 radiation data exist?
- **QX:** Has anyone compared CLARIFi with Yard, or quantified the overlap between Yard, CLARIFi and NCI-60?

## B2. Search log (2026-10-21)

| # | Source | Query / endpoint | Hits | Use |
|---|---|---|---|---|
| S1 | Europe PMC REST | `yard AND "vulnerability of cancer to DNA damage"` | 1 | Yard record |
| S2 | Europe PMC | `PMC4848553/fullTextXML` (read to character 100,000 of 141,413; the remainder is references) | – | Yard methods, supplement list |
| S3 | Europe PMC | `MED/27109210/citations` | 143 | Reuse of the Yard data |
| S4 | Europe PMC | `MED/39668120/citations` | 3 (including the self-record) | Papers citing CLARIFi |
| S5 | Europe PMC | `PMC11875790/fullTextXML` | – | CLARIFi methods and results |
| S6 | Europe PMC | DOI OR-query for 4 earlier Oike-group papers | 4 | Earlier work |
| S7 | Europe PMC | `"CLARIFi" AND (radiosensitivity OR SF2)` | 4 (2 relevant) | Users of CLARIFi |
| S8 | Europe PMC | `"mSF2" OR (AUTH:"Oike T" AND (SF2 OR radiosensitivity) AND PUB_YEAR:[2020 TO 2026])` | 84 (about 12 relevant) | Oike-group work |
| S9 | Web (extended) | `CLARIFi radiosensitivity database mSF2 Oike cell lines machine learning` | 9 | Users of CLARIFi |
| S10 | Europe PMC | `Yard AND NCI-60 AND radiosensitivity AND (overlap…)` | 3 | Overlap question |
| S11 | Europe PMC | PMC10763485 (Kolnohuz); PMC8921666 (RadSigBench; read to character 100,000 of 125,196) | – | Follow-up methods |
| S12 | PMC HTML | PMC8128135 (Manem 2019) | – | RadioGx |
| S13 | Europe PMC | `AUTH:"Amundson SA" AND NCI AND radiation survival AND PUB_YEAR:2008` | 3 | NCI-60 |
| S14 | AACR | Amundson 2008 full text | HTTP 403 | Not read |
| S15 | NCBI E-utilities | `esearch db=gds GSE184119[ACCN]`; `esummary` | 30 UIDs | GSE184119 |
| S16 | Europe PMC | `EXT_ID:32537359 OR EXT_ID:35127999`; PMC8803966 | 2 | Publication behind GSE184119 |
| S17 | Europe PMC | Fibroblast radiosensitivity × toxicity/fibrosis titles, sorted by citation | 19 | Normal-cell SF2 vs toxicity |
| S18 | Europe PMC | `TITLE_ABS:"moringa" AND (radioprotect* OR "gamma radiation" OR "ionizing radiation" OR radiosensiti* OR radiotherapy OR "radiation-induced" …)` | 2 pages read | Moringa and radiation |
| S19 | Web ×4 | Phrases from the original manuscript title; V79/DU145/MCF-7 + DCM + irradiated; "proliferation enhancement factor"; thesis | 0 matches | Publication status of the Moringa manuscript |
| S20 | Europe PMC | `moringa AND (V79 OR "DU145") AND (irradiat* OR "2 Gy")` | 16 (0 matches) | As S19 |
| S21 | Crossref | DOIs for ncomms11428, s12885-023-11634-3, 0008-5472.CAN-07-2120, aij.2014.262, dib.2022.107828 | – | DOI checks |
| S22 | Web | `PRISM pooled barcoded … ionizing radiation` | 0 radiation screens | PRISM-type work |

**Limitations:** Google Scholar not queried; Europe PMC citation lists miss non-indexed citers; paywalled full texts (Amundson 2008, Johansen, Russell, Rødningen, Forrester) read at abstract level only.

## B3. Topic 4: Yard et al. 2016 and reuse

**Yard BD, Adams DJ, Chie EK, …, Hammerman PS, Abazeed ME.** A genetic basis for the variation in the vulnerability of cancer to DNA damage. *Nat Commun* 2016;7:11428. DOI 10.1038/ncomms11428 [V-CR; CC BY 4.0]; PMID 27109210; PMC4848553 [V-EPMC].

| Field | Extraction |
|---|---|
| Samples | 533 lines, 26 cancer types. 87.8% genotype-matched to references; 6 suspect lines genotyped and matched [FT] |
| Assay | **ATP-based CellTiter-Glo**, 384-well; called a "High-throughput proliferation assay". **Not pooled or barcoded; not clonogenic.** Three seeding densities (25–225 cells/well), ≥ 4 replicates [FT] |
| Radiation | ¹³⁷Cs γ at 0.91 Gy/min; 1, 2, 3, 4, 5, 6, 8, 10 Gy, log₂-transformed [FT] |
| Time point | 9 days after irradiation [FT] |
| Endpoint | **Integral survival** (trapezoidal AUC, 0–7). No SF2 or LQ fit. The 0 Gy normalisation is not stated explicitly [I] |
| Clonogenic comparison | 15 lines: r = 0.85 (single run), 0.89 (mean of two) [FT]. Platform precursor: Abazeed et al. 2013 (R12) |
| Analysis | Information coefficient with permutation test, ssGSEA, CCLE SCNA, mutations and expression. **No ML prediction model** [FT] |
| Findings | 5–7-fold variation within lineages; fSCNA vs integral survival r = 0.27; KEAP1/NFE2L2 and AR associations [FT] |
| Supplements | SI PDF (Supplementary Figures 1–11); Supplementary Data 1–10 (.xlsx, s2–s11). **SD1 = "CCLE cell lines profiled and radiation sensitivity data".** Files not opened |
| Data availability | No formal statement; genomic data pointed to the CCLE site [FT] |

**Reuse of the Yard data** (all [V-EPMC]):

| Paper | Data / endpoint | Methods | Key results (as read) | Overlap check, tissue baseline, stability |
|---|---|---|---|---|
| Manem VS, et al. *Cancer Res* 2019;79(24):6227-6237. DOI 10.1158/0008-5472.can-19-0179; PMID 31558563; PMC8128135 (RadioGx) | Yard lines refitted with the LQ model | LQ fit, GSEA. No ML | 498/533 lines retained; AUC–SF2 ρ = 0.92; median α/β 10.14. Agreement with Yard's clonogenic subset: R ≥ 0.8 for AUC (n = 15), SF2 (n = 12), SF4 and SF6; SF8 R = 0.64 (n = 11) | Not applicable; code at github.com/bhklab/RadioGx |
| Spratt DE, Speers C. *Cancer Res* 2019;79(24):6076-6078. DOI 10.1158/0008-5472.can-19-3277; PMID 31836601 | Commentary | – | – | – |
| Kolnohuz A, et al. *BMC Cancer* 2024;24:2 (R15) | Training: Yard "Cleveland" 511 lines, 23 tissues. Validation: NCI-60, 60 lines. LQ-fitted AUC | Linear model on 22 genes; 10 × 10-fold CV with **feature selection inside the folds** | C-index 0.65 (CV), 0.61 (NCI-60) | **No overlap check reported; no tissue baseline; no stability analysis; CLARIFi not mentioned** |
| **O'Connor JD, Overton IM, McMahon SJ.** RadSigBench: a framework for benchmarking functional genomics signatures of cancer cell radiosensitivity. *Brief Bioinform* 2022;23(2):bbab561. DOI 10.1093/bib/bbab561; PMID 35066588; PMC8921666 | CCLE/Yard mean inactivation dose; NCI-60 SF2 (GSE32474 expression) | Seven published signatures re-fitted (linear, PLS-SVM, PCR) and benchmarked against resampled random signatures; 3-fold CV | **Mean out-of-sample R² 0.01 (CCLE) and 0.00 (NCI-60). Published signatures performed no better than random gene sets** | No overlap quantified; anatomical site suggested but not tested. **Important prior: expect a weak signal** |
| Gopal P, et al. *Clin Cancer Res* 2022;28(24):5343-5358. DOI 10.1158/1078-0432.ccr-22-1914; PMID 36222846 | 488 alleles edited into BEAS-2B cells | Gene editing + radiation profiling | KEAP1 and CTNNB1 allele effects [ABS] | Not applicable |
| Yard BD, et al. *Cancer Res* 2019;79(21):5640-5651. DOI 10.1158/0008-5472.can-19-0859; PMID 31387923 | Ra-223 α-particles, 28 lines | – | Median RBE 10.4 [ABS] | Not applicable |

**Count discrepancy [I].** The same dataset appears with different line counts:
- Yard: 533 lines, 26 types, doses 1–6, 8 and 10 Gy.
- Manem: 498 lines, 17 histologies.
- Kolnohuz: 511 lines, 23 tissues, doses listed as 1, 2, 3, 4, 6, 8 Gy.

The provenance record must name which version is used (original Supplementary Data 1, or the RadioGx refit).

**PRISM-type pooled radiation screen:** none found (S22). This is an absence of evidence, not proof that none exists.

## B4. Topic 5: CLARIFi and the Oike group

**Oike T, et al.** *Cancer Sci* 2025;116(3):690-697 (R17); full text re-read on 2026-10-21 [FT].

| Field | Extraction |
|---|---|
| Compilation | PubMed searched on 2018-12-30 for each of 1,048 CCLE lines. 33,284 papers screened by a deep-learning classifier plus manual review → **926 studies** |
| Inclusion | Clonogenic SF2 after photons. Concomitant reagents, plasmids and siRNA excluded; vehicle, scramble and empty-vector controls allowed |
| Value extraction | From text or digitised curves, to 2 decimal places |
| Output | **285 lines** (263 solid, 22 blood), 28 cancer types; median SF2 per line |
| Values per line | Shown only graphically (Fig. 1C, "Number of papers per SF2-available cell line"). Whether the median is taken over papers or over values is **not stated** |
| Comparison with in-house SF2 | Spearman r = 0.50 (n = 23); ≥ 3 papers: r = 0.60 (n = 19) |
| **Comparison with Yard** | **Spearman r = 0.28, p < 0.001, n = 187; ≥ 3 papers: r = 0.35, n = 84.** The authors: Yard's ATP assays "do not directly reflect the loss of colony-forming ability" |
| Omics analysed | NFE2L2 and SQSTM1 only. mRNA: n = 260, r = 0.086 (NS) and r = 0.081 (NS). Protein: NFE2L2 r = 0.25 (n = 68); SQSTM1 r = 0.20 (n = 141) |
| Other | mSF2 lower in blood lines than solid lines (p < 0.0001). No multiplicity correction. **No predictive ML** |
| Data | Points to researchmap.jp. Data S1 = search list; **Data S2 = the 926 papers** (may allow reconstructing values per line) |

Earlier Oike-group methods papers [V-EPMC; ABS]:
- Nuryadi 2018, *Oncotarget* 9:13706 (PMID 29568388): A549; SF2 CV < 30%.
- Komatsu 2019, *Radiother Oncol* 139:87 (PMID 31431384): literature-mining pipeline.
- Matsui 2019, *IJMS* 20:4148 (PMID 31450688): 620 experiments; CV < 30%.
- Anakura 2019, *IJMS* 20:3635 (PMID 31349558): EGFR-mutant vs wild-type NSCLC.
- **Oike 2020, *J Radiat Res* 61:828 (DOI 10.1093/jrr/rraa064; PMID 32823284):** audit of 1,672 papers. 30.5% did not report replicates and 32.3% did not report dose rate. This bears directly on mSF2 uncertainty.
- Oike 2020, *J Pers Med* 10:171 (PMID 33076277): plating before vs after irradiation had a negligible effect.

Later papers citing CLARIFi:
- Hinoto R, et al. *Med Phys* 2026;53(8):e70619. DOI 10.1002/mp.70619; PMID 42535578. Uses a CLARIFi-derived variance of NSCLC radiosensitivity (41 lines) for tumour-control-probability modelling. No expression ML.
- Debbi K, et al. *Crit Rev Oncol Hematol* 2025;216:104948 (PMID 40953756). A review; CLARIFi is not mentioned in the abstract.
- **No paper trains a molecular predictor on CLARIFi mSF2.**

## B5. Topic 9: normal-cell radiation responses

**GSE184119** [V-GEO]:
- Homo sapiens, RNA-seq, GPL20301, 28 samples, released 2021-09-23.
- Six normal cell types × (0 Gy, 10 Gy) × 2 biological replicates, plus 5 × 2 Gy arms for LEC and ADSC.
- Publication: Shukla L, et al. *Data Brief* 2022;41:107828 (DOI 10.1016/j.dib.2022.107828; PMID 35127999; PMC8803966); corrigendum DOI 10.1016/j.dib.2022.108358.
- Cells at passage 2–5; RNA at 4 h; Illumina HiSeq; limma-voom; code at github.com/mei-du/radiation.
- **No viability, clonogenic or proliferation endpoint** [FT].
- Companion paper: Shukla L, et al. *Plast Reconstr Surg Glob Open* 2020;8(3):e2706 (PMID 32537359).

**Normal fibroblast SF2 vs normal-tissue toxicity** [V-EPMC; ABS]:

| Citation | n | Assay | Finding |
|---|---|---|---|
| Johansen J, et al. *Radiother Oncol* 1996;40(2):101-109. DOI 10.1016/0167-8140(96)01777-x; PMID 8884963 | 31 | Clonogenic SF3.5 of fibroblasts | Correlated with fibrosis (rs = −0.46, P = 0.009) |
| Russell NS, et al. *Int J Radiat Biol* 1998;73(6):661-670. DOI 10.1080/095530098141915; PMID 9690684 | 79 | Clonogenic SF2 | SF2 ratio 0.80 (95% CI 0.60–1.07, P = 0.13): "limited usefulness" |
| Haikonen J, et al. *Int J Cancer* 2003;103(6):784-788. DOI 10.1002/ijc.10890; PMID 12516099 | 15 matched pairs | Clonogenic SF2 and AUC, fibroblasts vs HNSCC | Fibroblasts more sensitive in 14/15 pairs; weak correlation |
| Rødningen OK, et al. *Radiother Oncol* 2008;86(3):314-320. DOI 10.1016/j.radonc.2007.09.013; PMID 17963910 | 31 | Radiation-induced expression | 18-gene fibrosis classifier |
| Forrester HB, et al. *Radiother Oncol* 2014;111(2):186-193. DOI 10.1016/j.radonc.2014.03.007; PMID 24835153 | 6 | Basal expression | 8 candidate genes |

Also from Part A: Tobiasz 2023 (R21), CNV → SF2 in 129 normal fibroblast strains.

[I] Evidence that fibroblast SF2 predicts toxicity is mixed. **No public normal-cell clonogenic SF2 set linked to DepMap-style omics was found.**

## B6. Topic 10: Moringa and plant extracts with radiation

**Status of the original manuscript.** No published version, abstract or thesis was found (S19, S20). Authors, venue and DOI remain **unknown**.

| Citation | Model | Radiation | Endpoint | Finding as stated [ABS] |
|---|---|---|---|---|
| Rao AV, Devi PU, Kamath R. *Indian J Exp Biol* 2001;39(9):858-863. PMID 11831365 | Mice; methanolic leaf extract | 4 Gy γ, whole body | Chromosome aberrations, micronuclei | Fewer aberrations |
| Sinha M, et al. *J Med Food* 2011;14(10):1167-1172. DOI 10.1089/jmf.2010.1506; PMID 21861723 | Mice | 5 Gy ⁶⁰Co | Liver oxidative markers | "Protected against" damage |
| Sinha M, et al. *Indian J Exp Biol* 2012;50(3):209-215. PMID 22439436 | Mice | 5 Gy | Lipid peroxidation, GSH | Restored GSH |
| Elwan AM, et al. *Prog Biophys Mol Biol* 2018;140:142-149. DOI 10.1016/j.pbiomolbio.2018.06.003; PMID 29885346 | Rats | Not in abstract | Bone-marrow properties | Improvement |
| Boonsirichai K, Jetawattana S. *Atom Indonesia* 2014;40(1):7. DOI 10.17146/aij.2014.262 [V-CR] | **MCF-7** | γ 2–8 Gy | γH2AX foci | Foci reduced by about 15–30%: the extract **protected tumour cells** |
| Hagoel L, et al. *Integr Cancer Ther* 2019;18:1534735419828829. DOI 10.1177/1534735419828829; PMID 30862207 | PANC-1; nude mice | Not in abstract | Clonogenic and XTT survival | The combination reduced survival; no normal cells tested |
| Bakr NM, et al. *Heliyon* 2024;10(6):e27495. DOI 10.1016/j.heliyon.2024.e27495; PMID 38510057 | Rats | 20 Gy fractionated | Periodontal histology | Less damage |
| Richards VJ, et al. *Toxicol Mech Methods* 2026;36(3):389-402. DOI 10.1080/15376516.2025.2601989; PMID 41481328 | Human lymphocytes | 2 Gy X-rays | Aberrations, strand breaks | Reduced |
| Darul Raiyaan GI, et al. *Appl Radiat Isot* 2025;226:112133. DOI 10.1016/j.apradiso.2025.112133; PMID 40849986 | Fish | ⁶⁰Co | Micronucleus, comet | Protective, but less than amifostine |

[I] No study treated normal **and** tumour cells on the same clonogenic endpoint. One study (Boonsirichai & Jetawattana 2014) reports protection of a tumour line, MCF-7, which is one of the lines in the Moringa manuscript. This supports the rule against claiming selective radioprotection.

Reviews [V-EPMC]:
- Kuruba & Gollapalli 2018, *Radiat Oncol J* 36:265 (PMID 30630265).
- Samarth et al. 2015, *Drug Des Devel Ther* 9:5355 (PMID 26451089).
- Stasiłowicz-Krzemień et al. 2024, *IJMS* 25:6937 (PMID 39000045).
- Stohs & Hartman 2015, *Phytother Res* (PMID 25808883), which lists "radioprotective" among Moringa's activities.

## B7. NCI-60 radiation data

- **Amundson SA, et al.** *Cancer Res* 2008;68(2):415-424 (R5). NCI-60 + 3 lines; clonogenic survival at 2 and 8 Gy γ [ABS]. RadSigBench lists n = 63, clonogenic SF2 and D₀.
  - **Full text not read (HTTP 403).** Who performed the assays, the per-line values and the full dose set are unverified. Kolnohuz describes NCI-60 doses of 2, 4 and 6 Gy.
  - GEO GSE7505 (63 samples; PMID 18199535) holds the expression data. Whether its sample metadata contain SF2 is unverified (curator).
- The primary source of the NCI-60 SF2 vector used by Zhang 2014 and RadSigBench is **unresolved** (RadSigBench reference 49 was not read).
- Kim & Chung 2022b, *Nucl Eng Technol* 54(8):3027-3033 (DOI 10.1016/j.net.2022.03.019) [V-CR, bibliographic only].

## B8. Direct answers

- **Has anyone compared CLARIFi with Yard?** Yes, but only as a correlation of the two endpoints, in the CLARIFi paper itself (r = 0.28, n = 187). No other comparison was found, and no comparison of model predictions across the two endpoints.
- **Has anyone quantified the overlap between Yard, CLARIFi and NCI-60?**
  - Yard ∩ CLARIFi: implicitly 187 lines; matching method not described.
  - Yard ∩ NCI-60: not reported. Kolnohuz 2024 trained on Yard and validated on NCI-60 without reporting an overlap check, so shared lines may not have been removed ([I], possible leakage).
  - Three-way overlap: **no published quantification found.**

## B9. Unverified leads (do not cite)

1. Research Square preprint rs-7609771/v1, "Machine Learning Classification of Radiosensitivity in Cancer Cell Lines": content not retrievable.
2. Kim & Chung 2022 "59 lines, 35 overlapping Torres-Roca" (from a search snippet only).
3. The primary NCI-60 SF2 source; the Amundson 2008 methods.
4. Contents of Yard Supplementary Data 1; doses and line counts of the RadioGx version.
5. A 2015 rat liver-fibrosis study combining Moringa with low-dose γ; an aqueous flower-extract fibroblast study (search snippets only).
6. Any version of the original Moringa manuscript: none found.
7. Content of the GSE184119 corrigendum.

---

# §C. Consolidated novelty answers (Parts A + B)

| Question | Answer | Evidence |
|---|---|---|
| Has CLARIFi been compared with Yard? | **Yes, as a label correlation only** (r = 0.28, n = 187; r = 0.35, n = 84 with ≥ 3 papers) | R17 |
| Tissue-informed prediction baselines for radiation? | **Not found.** Tissue was used only as an in-sample covariate (R2, R4) or suggested (RadSigBench). A drug-response template exists (P1) | R2, R4, P1, RadSigBench |
| Expression-based prediction across independent datasets? | **Partly done.** Yard → NCI-60 (R14, R15; C-index about 0.6), without overlap checks. RadSigBench found published signatures no better than random gene sets (R² ≈ 0) | R14, R15, RadSigBench |
| Models trained or tested on CLARIFi mSF2? | **Not found** | S7, S9, Part A #7 |
| Overlap-controlled cross-dataset or cross-assay model evaluation? | **Not found** | B8 |
| Stability of explanations for radiation models? | **Not found** | A5(c) |

**What the evidence predicts (interpretation, not a result).** Four findings point the same way:
- RadSigBench found R² ≈ 0;
- the two strongest candidate genes have mRNA r ≈ 0.08 with mSF2;
- CLARIFi and Yard agree only weakly (r = 0.28);
- mSF2 is noisy (r = 0.50 against in-house SF2).

**Any molecular signal beyond tissue is likely to be small.** A study design that treats a null result as a valid, pre-specified outcome is therefore the defensible choice.

**Before the novelty claim enters the protocol:** run a Google Scholar / Scopus / Web of Science pass, chase forward citations of R14, R15, R17 and RadSigBench, and verify every quantitative value against the PDFs.
