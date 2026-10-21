# Scientific linkage to the original Moringa oleifera study

**Role of this document.** It is a sourced record of the original experimental study, and an account of how that study motivates Explainable Radiosensitivity ML. **The Moringa data are motivation only.** They are never used as training, calibration or validation data for any model in this project.

## 0. Source and how to read the citations

| Item | Value |
|---|---|
| File | `references/source_manuscripts/moringa_original.pdf` (gitignored; provenance in `references/source_manuscripts/manifest.yaml`) |
| SHA-256 / MD5 | `7f644f55a2e1eca3cfd95ba48a74096cedf676bd3fac9910b5e6b8db8e870fb9` / `1ae1f270e77fa1e14095be400adb6eea` |
| Form | Scanned manuscript, 8 PDF pages |
| **Pages present** | Printed pages **1, 2, 4, 5, 6, 13, 14, 15** |
| **Pages missing** | Printed page **3** (plant material, extraction and cell-culture methods would be expected here) and printed pages **7–12** (end of Discussion, conclusions, references) |
| Authors, journal, DOI, date | **Not shown** on the supplied pages. Publication status unknown |
| Legibility | Body text legible despite scan streaks and bleed-through. In Figures 1 and 2, the 0 Gy and 2 Gy series **cannot be told apart** (identical grayscale markers and line style) |

**Citation format:** "p. N/M" means PDF page N, printed page M. Mapping:

| PDF page | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Printed page | 1 | 2 | 4 | 5 | 6 | 13 | 14 | 15 |

**Labels:**
- **[M]** measured result reported in the manuscript;
- **[A]** the authors' interpretation;
- **[P]** this project's commentary or hypothesis;
- **[NS]** not stated in the supplied pages.

Nothing marked [NS] has been reconstructed.

Extraction by Claude Code. Every item was checked against the page images by the radiobiologist agent (2026-10-20); corrections are incorporated.

## 1. Title and objectives

- **Title** (p. 1/1): "Dichloromethane seed and leaf extracts of *Moringa oleifera* (Lam) enhance proliferation in irradiated rodent fibroblasts *in vitro*".
- **Keywords** (p. 1/1): "*Moringa oleifera*, dichloromethane, seed extract, leaf extract, radiation-enhanced proliferation, wound healing".
- **Motivation** (p. 1/1): "preoperative radiotherapy is often associated with wound healing complications". The aim is to identify agents that "could mitigate radiation-induced wound healing difficulties by promoted cell proliferation".
- **Objective** (p. 2/2): crude dichloromethane (DCM) seed and leaf extracts "were assessed for their effect on cell proliferation (a requirement for wound healing and tissue remodeling)" in V79, DU145 and MCF-7 cells, unirradiated and irradiated (abstract, p. 1/1).

**[P]** The study is framed around **wound healing and radiation-modified proliferation**, not around clonogenic radiosensitivity or a demonstrated selective radioprotective effect. This repository's former name ("selective radioprotection") goes further than the manuscript's own framing.

## 2. Cell lines

| Line | Manuscript description | Notes |
|---|---|---|
| V79 | "apparently normal Chinese hamster lung fibroblasts" (p. 2/2) | Also called "apparently normal **murine** cell line" in the Table 1 and 2 captions (p. 6/13) and "apparently normal **rodent** fibroblasts" (p. 5/6). **Inconsistent:** hamster is not murine. **[P]** V79 is an established hamster line, not normal human tissue *[citation needed for line origin]* |
| DU145 | "human prostate cancer cells" (p. 2/2) | |
| MCF-7 | "human mammary adenocarcinoma cells" (p. 2/2) | |

[NS]: line sources, authentication, passage numbers, mycoplasma status, culture media, serum, temperature and CO₂ (probably on the missing printed page 3).

## 3. Extracts

- "crude dichloromethane (DCM) seed and leaf extracts" (p. 2/2).
- Before use: "reconstitution in phosphate buffered saline (PBS) and sterile filtration through 0.22-µm nylon filter membranes" (p. 3/4).
- [NS]:
  - plant source and authentication;
  - extraction procedure, solvent removal, yield, storage;
  - chemical characterisation;
  - any vehicle-only or PBS-only control.

## 4. Treatment and irradiation

- **Concentrations:** "0 to 100 µg/ml" (p. 3/4). The individual concentrations used are [NS] in the text.
- **Sequence** (p. 3/4):
  - One plate per cell line per extract was treated with extract and "reincubated without irradiation (0 Gy)".
  - The second plate was "similarly treated with extract … and immediately irradiated to 2 Gy of X-rays".
  - No washout or medium change is described, so the extract was apparently present until the 72-h endpoint.
- **Irradiator** (p. 3/4): "Precision MultiRad 160 X-irradiator (Precision X-Ray Inc., Branford, CT, USA)"; "A dose rate of 1 Gy/min"; "total volume of culture medium per well was 2 ml".
- [NS]: tube voltage, current, filtration, geometry, dosimetry and calibration, sham handling of the 0 Gy plate, temperature.
- **Concentration inconsistencies** (as printed, not corrected):
  - Results: enhancement "At concentrations of 30-50 **mg/ml**" and growth increased "as extract concentration increased to 50 **mg/ml**" (p. 4/5);
  - Abstract: "25-50 µg/ml" (p. 1/1);
  - Discussion: "higher than 20 µg/ml" (p. 5/6);
  - Methods and figure axes: µg/ml.

## 5. Proliferation assay (crystal violet)

**Procedure** (p. 3/4):
- "Exponentially growing cells in 25-cm² tissue culture flasks were trypsinised into single-cell suspensions and seeded in two 24-well Corning microplates (2 plates per cell line per extract; 3 wells per sample) at 5 000 cells per well."
- Attachment: 3 h.
- **Incubation:** 72 h after treatment.
- **Staining:** media decanted; PBS wash; "fixed for 20 minutes in 70% ethanol, stained in 0.5% crystal violet, and rinsed under tap water".
- **Readout:** stain "dissolved overnight in 1 ml of 10% sodium dodecyl sulphate"; **optical density (OD) at 590 nm**.

**Controls** (p. 3/4): "Unirradiated and 2-Gy cultures (three wells each) that did not receive extract served as negative controls for 0-Gy and 2-Gy cultures that were treated with extract, respectively."

**Control subtraction** (p. 3/4):
- "The mean (±SE) OD of each triplicate control was subtracted from that of each of the corresponding extract treated samples."
- "Negative and positive changes in OD signify inhibition and promotion of cell growth in comparison to controls, respectively."

**Replicates [M]:**
- The unit is 3 wells per sample, on 2 plates per cell line per extract (one plate per dose).
- **No independent experimental repeats** (separate days, passages or irradiation sessions) are described.
- **[P]** Dose is confounded with plate.

## 6. PEF: definition and calculation

**Definition** (p. 3/4):
- The change in OD was plotted against extract concentration, "and the area under each plot, *A*D (*A*2Gy for the 2-Gy samples or *A*0Gy for the 0-Gy samples) was determined and used as an indicator of cell proliferation".
- "**PEF = *A*2Gy/*A*0Gy**".
- "*PEF* values of >1.0, 1.0, and <1.0 indicate an increase, no effect, and reduction in proliferation, respectively."

**What PEF compares [P]:**
- Each *A*D is the extract response **relative to its own dose-matched untreated control**.
- PEF therefore compares the extract's effect in irradiated cultures with its effect in unirradiated cultures, within one cell line.
- PEF > 1 does **not** mean growth above untreated control.

**Not explained in the supplied pages [NS]:**
- how *A*D was integrated (method, limits, signed or absolute values, any offset);
- how its SE was obtained;
- why its unit is printed as "µg/ml".

**Unresolved inconsistency [P]:**
- The tabulated *A*D values are all **positive** (Tables 1–2), but the plotted change in OD is mostly **negative** for DU145 and MCF-7 with seed extract (Figure 1B–C, p. 7/14).
- By the manuscript's own sign rule, that implies negative areas.
- The leaf *A*D values (≈37–47) are also several times the seed values (≈9–14), although the plotted leaf changes are not larger.
- These points cannot be reconciled without the missing pages or the raw data.

## 7. Statistics

Pages p. 3/4 – p. 4/5:
- "GraphPad Prism (GraphPad Software, San Diego, CA, USA)". The version is [NS].
- "Data were presented as the mean difference between controls and extract treated samples (triplicate per sample). The means were compared using the unpaired two-sided Student's *t*-test. A *P*-value of <0.05 indicated a statistically significant difference … Where applicable, errors were calculated using appropriate error propagation formulae."
- [NS]: the n and degrees of freedom of each test, assumption checks, and multiplicity correction (3 lines × 2 extracts).
- **[P]** The tests appear to treat technical wells as replicates.

## 8. Reported results [M]

**Table 1, DCM seed extract, 2 Gy vs 0 Gy** (p. 6/13). *A*D is reported in "µg/ml" as printed.

| Cell line | *A*D, extract + 2 Gy | *A*D, extract + 0 Gy | *P* | PEF |
|---|---|---|---|---|
| V79 | 13.73 ± 0.07 | 10.95 ± 0.36 | 0.0016 | 1.25 ± 0.04 |
| DU145 | 9.64 ± 0.09 | 8.61 ± 0.18 | 0.0072 | 1.12 ± 0.03 |
| MCF-7 | 9.93 ± 0.05 | 8.60 ± 0.05 | <0.0001 | 1.16 ± 0.01 |

**Table 2, DCM leaf extract** (p. 6/13).

| Cell line | *A*D, extract + 2 Gy | *A*D, extract + 0 Gy | *P* | PEF |
|---|---|---|---|---|
| V79 | 47.00 ± 1.05 | 37.22 ± 0.89 | 0.0021 | 1.26 ± 0.04 |
| DU145 | 39.20 ± 0.16 | 43.50 ± 0.32 | 0.0003 | 0.90 ± 0.01 |
| MCF-7 | 38.31 ± 1.34 | 38.82 ± 1.42 | 0.8072 | 0.99 ± 0.05 |

**Notes on the tables:**
- Table notes (p. 6/13): *A*D were "compared using the unpaired two-sided Student's *t*-test. Errors in *PEF* were calculated using an appropriate error propagation formula."
- What "±" denotes in the tables is [NS]. The figures use "± SE".
- Each PEF equals the ratio of its two tabulated *A*D values to two decimal places (arithmetic consistency check of reported numbers only; no data were analysed).

**Results text [M]** (p. 4/5):
- **Seed, V79 unirradiated:** "a reduction in cell growth was observed at low and high concentration", with enhancement at intermediate concentrations (unit inconsistency, §4).
- **Seed, V79 irradiated:** "consistently increased cell growth as extract concentration increased to 50 mg/ml".
- **Seed, DU145 and MCF-7:** "either showed no change or diminished growth relative to controls, when treated with extract with or without irradiation".
- **Seed PEF:** "Treatment of all cell lines with the extract yielded between 12 and 25% enhancement in the proliferation of irradiated cells, in comparison with unirradiated cells … statistically significant (*P* ≤ 0.0072)".
- **Leaf, unirradiated:** reduction (V79), increase (DU145), no effect (MCF-7).
- **Leaf, irradiated:** increase (V79), decrease (DU145), no change (MCF-7). Restated as PEF 1.26 ± 0.04 (*P* = 0.0021), 0.90 ± 0.01 (*P* = 0.0003) and 0.99 ± 0.05 (*P* = 0.8072).

**Figures 1–2** (p. 7/14, p. 8/15):
- They show "mean change in OD ± SE of triplicate samples"; the dashed line represents untreated cultures.
- Individual point values were **not** extracted, and the 0 Gy and 2 Gy series cannot be reliably identified in the scan.

## 9. Normal versus malignant responses

| | V79 (hamster fibroblast) | DU145, MCF-7 (human carcinoma) |
|---|---|---|
| Seed, PEF [M] | 1.25 | 1.12, 1.16 (both > 1, *P* ≤ 0.0072) |
| Seed, growth vs untreated control [M] | Increased at 2 Gy (p. 4/5) | "no change or diminished growth" (p. 4/5); "generally lower than that in untreated controls" (p. 5/6) |
| Leaf, PEF [M] | 1.26 | 0.90 (DU145), 0.99 (MCF-7, *P* = 0.8072) |

**[P] The word "enhancement" is used for two different quantities.**
- **PEF** (the 2 Gy arm vs the 0 Gy arm): by this measure, the seed extract "enhanced" all three lines.
- **Growth relative to untreated control:** by this measure, only V79 increased.

The Discussion's "only in the apparently normal rodent fibroblasts" (p. 5/6) refers to the second; the Results' "all cell lines" (p. 4/5) refers to the first. In PEF terms, only the **leaf** extract shows a normal/malignant difference. That difference compares one hamster fibroblast line with two human carcinoma lines, so species, tissue of origin, phenotype and malignancy are confounded.

## 10. Authors' interpretations [A]

All of these are interpretations; none was measured directly:
- Seed extract: potential "enhancer of tissue remodeling in surgeries after radiotherapy" (p. 5/6).
- Seed extract: "cytotoxic towards malignant cells", especially "higher than 20 µg/ml"; "The extract could promote tumour control" (p. 5/6).
- Leaf extract: "protects the apparently normal fibroblasts from adverse effects of ionising radiation", "about 26% increase in proliferation of irradiated cells" (p. 5/6).
- Abstract: both extracts "show potential to serve as wound healing promoters in pre-operative radiotherapy, as they preferentially enhance proliferation in irradiated fibroblasts"; "Further studies on larger panels of cell lines and animal models might assist in validating the possible use of these extracts in the clinic" (p. 1/1).
- The authors note that the leaf result "contrasts with several studies demonstrating significant antiproliferative and cytotoxic effects of *M. oleifera* leaf extract in human tumour cells" (p. 5/6).

**[P]** The supplied pages contain **no**:
- cytotoxicity, apoptosis or viability assay;
- clonogenic survival;
- DNA-damage or repair readout;
- wound or migration assay;
- normal human cell line;
- mechanistic experiment.

**The manuscript does not establish any molecular mechanism**, clinical radioprotection, wound-healing efficacy or selective tumour protection.

## 11. Limitations [P]

Reviewed by the radiobiologist agent.

1. **Missing pages.** Printed pages 3 and 7–12 are absent: extract preparation, culture conditions, the end of the Discussion, conclusions and references.
2. **Endpoint.** The 72-h crystal-violet OD measures adherent biomass. It mixes proliferation, attachment, cell size and death, and radiation-induced enlargement can raise OD without survival.
3. **Unclear computation.** How *A*D was computed (units, sign, SE) is not described and does not match the figures (§6).
4. **Pseudo-replication and confounding.** Replicates are technical wells; there are no independent repeats; dose is confounded with plate.
5. **Dose design.** One non-zero dose (2 Gy), no dose–response, and the extract present throughout. No dose-modifying factor can be derived.
6. **Missing controls.** No vehicle or cell-free interference control is described.
7. **Small, confounded design.** Three cell lines; the only "normal" line is also the only non-human line.
8. **Inconsistencies.** Concentration units (mg/ml vs µg/ml; 25–50, 30–50, >20 µg/ml) and species wording (hamster, murine, rodent) are inconsistent.
9. **Statistics.** No multiplicity correction; t-test n and degrees of freedom not reported.

## 12. PEF is not SF2

| | PEF (this manuscript) | Clonogenic SF2 (e.g. CLARIFi mSF2) |
|---|---|---|
| What is measured | Crystal-violet OD (biomass) 72 h after treatment | Fraction of cells forming colonies (unlimited proliferative capacity) after 2 Gy, normalised to plating efficiency at 0 Gy |
| Quantity | Ratio of integrated extract-vs-control OD differences, 2 Gy vs 0 Gy | Surviving fraction (0–1) |
| Conditions | With extract present | Untreated baseline (CLARIFi excludes studies with concomitant reagents) |
| Timescale | 72 h; lethally damaged cells still stain | Usually 1–3 weeks of colony growth |
| Interpretation | Extract-by-radiation interaction on biomass | Intrinsic radiosensitivity |

PEF and SF2 must never be equated, placed on one axis, pooled, or used as substitutes for each other (`docs/data_management.md` §5).

## 13. Scientific connection to the AI/ML investigation

Drafted by the research-director agent and adopted with minor edits.

**What the observations motivate.** In this study, the post-irradiation proliferative response to a plant extract differed between cell types. This is clearest for the leaf extract (PEF 1.26 in V79; 0.90 and 0.99 in the tumour lines). It raises a broader question: do cell lines differ in **intrinsic** radiation response, and do measurable molecular features explain those differences? That question is answerable with public data. A three-line extract study cannot answer it.

**Why the Moringa results do not validate an intrinsic radiosensitivity model:**
- **Endpoint:** a 72-h biomass ratio under extract is not clonogenic SF2.
- **Treated, not baseline:** the cells were modifier-treated, whereas public SF2 is an untreated baseline.
- **Species:** V79 is a hamster line, unlikely to have matched molecular profiles in human cell-line resources.
- **Size:** three lines, one dose, technical replicates only.

The Moringa measurements are therefore **never** training, calibration or validation data.

**How the ML aims relate:**

| Aim | Question | Link to the motivation |
|---|---|---|
| Prediction | Do molecular profiles predict experimentally measured clonogenic SF2 (CLARIFi mSF2, DepMap-identified lines) better than prespecified simple baselines, with splits by cell line? | Formalises "cell types differ in radiation response" on a valid endpoint |
| Cross-assay generalisation | Does performance carry over between SF2 sources, and between clonogenic and non-clonogenic endpoints? Reported as heterogeneity, not pooled | Directly addresses the PEF ≠ SF2 problem |
| Tissue of origin | How much signal remains beyond tissue of origin (tissue-only baselines, leave-one-tissue-out)? | The Moringa design confounds tissue, species and malignancy |
| Robust explanation | Are feature attributions stable across resamples, models and datasets? | Prevents over-reading a few features, as the extract study cannot separate effects |
| Pathways | Do stable attributions group into pathways relevant to differential radiation response? | Candidate determinants: **associations, not mechanisms** |

**Analyses that could generate hypotheses relevant to selective radioprotection** (hypotheses only; to be designed in phase_02):
- Contrast observed and predicted SF2, and attribution profiles, between tissue classes.
- Place DU145 and MCF-7 in the SF2 distribution, if they appear in CLARIFi. **To be checked by DepMap ID in phase_01**; not asserted here. V79 is not expected in DepMap.
- Identify pathway-level attributions that are stable across datasets, as candidates for differential response.

**Experiments needed to test any such hypothesis** (proposals, not results):
1. Multi-dose clonogenic survival with and without extract, giving linear-quadratic parameters and a dose-modifying factor.
2. Species- and tissue-matched normal/tumour pairs, assayed identically.
3. Vehicle and cell-free interference controls.
4. Schedule-by-concentration designs.
5. Independent biological repeats.
6. Chemical characterisation of the extracts.

Selective radioprotection would require treated normal **and** treated tumour measurements on the same endpoint.

**Wording guidance for the eventual paper:**
- **Use:** "motivated by"; "post-irradiation proliferative response"; "apparently normal hamster fibroblasts (V79)"; "hypothesis-generating"; "associated with predicted SF2"; "attribution stability"; "requires experimental testing".
- **Avoid:** "Moringa radioprotects normal cells"; "selective radioprotection" as a finding; "validated by Moringa data"; "radioresistance" for a PEF; "mechanism" for an attribution; PEF and SF2 used interchangeably.

*Record: radiobiologist (manuscript extraction and verification), research-director (§13 and framing). No literature search was performed; general cell-line background still needs citations.*
