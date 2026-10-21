# Phase 01 Moringa linkage: what an exploratory connection can and cannot be

**Status:** phase_01 draft for investigator review, 2026-10-21. Prepared by the **radiobiologist** subagent and written to disk by Claude Code. Cell-line accessions were added from the radiogenomics-curator's Cellosaurus queries.

This document extends `docs/moringa_scientific_linkage.md` (the verified manuscript extraction) and takes all its endpoint rules from `docs/phase_01_endpoint_compatibility.md`.

**The Moringa measurements remain motivation only.** They are never training, calibration or validation data for any model in this project. Nothing in this document was computed from data, no model was run, and no mSF2 value was read.

**Labels:**
- **[V]** verified from a cited primary source;
- **[M]** measured and reported in the Moringa manuscript;
- **[NS]** not stated in the supplied pages;
- **[P]** this project's reasoning;
- **[H]** a hypothesis, untested.

---

## 1. Limitations carried forward, unchanged

1. **Missing pages.** The source is a scanned 8-page PDF (`references/source_manuscripts/moringa_original.pdf`, SHA-256 `7f644f55…70fb9`). Printed page 3 and printed pages 7–12 are absent: plant material, extraction and culture methods, the end of the Discussion, the conclusions and the **entire bibliography**. Authors, journal, DOI and date are not shown, and the publication status is unknown.
2. **Incomplete bibliography.** The authors' evidential basis cannot be checked.
3. **Unverified extract preparation.** Plant source, authentication, extraction, solvent removal, yield, storage and chemical characterisation are all [NS]. Only reconstitution in PBS and 0.22-µm filtration are described. **No extract composition is asserted or inferred anywhere in this project.**
4. **Inconsistent concentration units.** The units disagree by up to 1000-fold and the conflict is unresolved:
   - Methods and figure axes: µg/ml;
   - Results: "30–50 mg/ml";
   - abstract: "25–50 µg/ml";
   - Discussion: "higher than 20 µg/ml".
5. **Inconsistent species description.** V79 is called "Chinese hamster lung fibroblasts", "murine" (table captions) and "rodent". Hamster is not murine. Cellosaurus: V79 is CVCL_2234, *Cricetulus griseus*. 62 Cellosaurus records match "V79" (e.g. V79-4, CVCL_2796), so the exact subline used is unresolved.
6. **Technical replicates; dose confounded with plate.**
   - Design: three wells per sample, two plates per cell line per extract, one plate per dose.
   - No independent biological repeats are described.
   - The t-tests appear to treat wells as replicates; n and degrees of freedom are [NS]; there is no multiplicity correction.
7. **Unexplained positive *A*_D vs negative plotted ΔOD.**
   - The tabulated *A*_D values are all positive, but the plotted ΔOD is mostly negative for DU145 and MCF-7 with seed extract.
   - Leaf *A*_D values (about 37–47) are several times the seed values (about 9–14), although the plotted changes are not larger.
   - The integration method, limits, sign convention and SE are [NS].
   - **This cannot be reconciled without the missing pages or the raw data.**
8. **PEF ≠ SF2.**
   - PEF is a 72-h interaction ratio of adherent biomass, measured with the extract present.
   - SF2 is a colony-formation survival fraction measured on untreated cells.
   - They must never be equated, pooled, co-plotted or substituted for each other. CLARIFi also **excludes** concomitant-reagent studies [V].
9. **Extract-modified proliferation ≠ intrinsic radiosensitivity ≠ clinical radioprotection.**
   - The manuscript measures only the first of these.
   - It contains no clonogenic, cytotoxicity, apoptosis, viability, DNA-damage, wound or migration assay, no normal **human** line and no mechanistic experiment.
   - **No mechanism is established**, and neither is clinical radioprotection, wound-healing efficacy or selective tumour protection.
10. **Design scale and confounding.**
    - Three lines and a single non-zero dose.
    - Extract present throughout; no vehicle, cell-free interference or washout controls.
    - The only "normal" line is also the only non-human line, so species, tissue of origin and malignancy are confounded.
    - No dose-modifying factor can be derived from a single dose.
11. **Figure legibility.** The 0 Gy and 2 Gy series cannot be told apart in Figures 1–2. Individual point values must not be extracted.

Framing points already on record:
- "Enhancement" refers to two different quantities. By PEF, seed extract "enhanced" all three lines. By growth relative to the untreated control, only V79 increased.
- By PEF, only the **leaf** extract shows a normal/malignant difference (V79 1.26; DU145 0.90; MCF-7 0.99, *P* = 0.8072).
- The repository's former name, "selective radioprotection", goes further than the manuscript's own framing (wound healing; radiation-modified proliferation).

---

## 2. What is being asked in phase_01

> Are the human cell lines used in the Moringa study represented in the public radiosensitivity resources this project will use, so that the Moringa experiment could later be *situated* (not validated) within a public distribution of intrinsic radiosensitivity?

This is an identifier question. It can be answered without touching any endpoint value.

---

## 3. Identifier findings (presence only; no values read)

| Moringa line | Species | Cellosaurus (r56, curator, verified) | DepMap | In CLARIFi? |
|---|---|---|---|---|
| MCF-7 | Human | CVCL_0031 | ACH-000019 | **Present** (`MCF7_BREAST`, 1 row) |
| DU145 | Human | CVCL_0105; 16 derived lines exist (e.g. DU145-R), so matching must be exact | ACH-000979 | **Present** (`DU145_PROSTATE`, 1 row) |
| V79 | **Chinese hamster** | CVCL_2234 (subline unresolved) | None | **Absent, as expected**: CLARIFi is built from human CCLE/DepMap lines |

Neither MCF-7 nor DU145 carried a Cellosaurus "Problematic cell line" comment when the curator queried them on 2026-10-21. The ICLAC v14 lookup is still outstanding.

**Method and limits.**
- Claude Code (`grep`, `cut`) and the radiobiologist (`rg -c`) independently confirmed that each identifier appears exactly once and that each name sits on the same row as its ID.
- **No mSF2 value was read, extracted, computed or reported.**
- The Moringa side gives no stock source, authentication, passage or mycoplasma status [NS]. **Identity between the Moringa stocks and the public lines rests on name alone and is not verified.**

Context [V]:
- Oike et al. note that MCF7 is among the lines most frequently used in radiation experiments.
- DU145 is in the Guerra Liberal & McMahon 2023 panel, whose Figure 1 illustrates large variation in published survival values.

---

## 4. What the connection can show

These hold strictly, and only after the gates in §7:

1. **Representation.** Two of the three Moringa lines are among the 285 CLARIFi lines. This is a statement about the coverage of the public resource.
2. **Contextual placement (possible, not done).** In phase_04, under investigator control, it would be technically possible to mark MCF-7 and DU145 on the CLARIFi mSF2 distribution. **Deliberately not computed here.** It would describe their intrinsic, untreated radiosensitivity as recorded in the literature, and nothing about the extract, PEF or V79.
3. **Motivational framing.** The general question (do cell types differ in radiation response, and do molecular features explain it?) is answerable on a valid endpoint with public data. A three-line, single-dose extract study cannot answer it.
4. **A worked illustration of endpoint discipline.** The same nominal dose and the same two human lines still give an entirely non-comparable endpoint.
5. **Optional qualitative pathway cross-reference** against GSE184119 (rule R6 in `docs/phase_01_endpoint_compatibility.md`). The dataset's parameters must be stated alongside: 10 Gy or 5 × 2 Gy, 4 h, normal skin and soft-tissue cells, n = 2. No cell-line-level join is possible.

## 5. What the connection cannot show

1. **It cannot validate anything.** PEF and mSF2 are incompatible endpoints.
2. **It says nothing about the extract.** mSF2 is an untreated baseline.
3. **It cannot address V79.** V79 is a hamster line with no human molecular profile.
4. **It cannot demonstrate selectivity.** That needs normal and tumour cells, both treated, on the same endpoint under the same conditions. None of the available sources supplies this.
5. **It cannot establish a mechanism.** Attributions are associations. Across unmodified lines, DNA-repair parameters did not correlate strongly with radiosensitivity; plating efficiency and %S phase did [V, Guerra Liberal & McMahon 2023].
6. **It cannot separate proliferation from survival.**
7. **It cannot be read across radiation qualities** without the caveats in §3.4 of the endpoint document.
8. **It cannot support any clinical statement.**

## 6. Hypotheses, labelled as such

- **[H1]** Cell lines differ in intrinsic clonogenic radiosensitivity, and part of this variation is associated with baseline molecular features. This is testable on public data with mSF2 as the target. It is the project's primary aim and does not depend on the Moringa study.
- **[H2]** The post-irradiation proliferative response to a plant extract differs between cell types. The Moringa observation is *consistent* with this but does not establish it.
- **[H3]** Any difference in extract response between normal and malignant cells would appear on a clonogenic endpoint as a dose-modifying factor that differs between matched normal and tumour cells. Entirely untested.
- **[H4]** Feature attributions that are stable across resamples, models and datasets will group into pathways relevant to differential radiation response. Such pathways would be candidate determinants only.

**Not hypothesised, and never to be written:**
- that Moringa extracts radioprotect normal cells;
- that PEF reflects radioresistance;
- that the extract has a known composition or mode of action;
- that any public dataset validates the Moringa results.

## 7. Wet-lab experiment required to test any of this

Reporting should follow the recommendations for drug–radiation combination studies (Stone et al. 2016, *Transl Oncol* 9:46–56, DOI 10.1016/j.tranon.2016.01.002, PMID 26947881).

1. **Clonogenic survival over multiple doses, with and without extract.**
   - 0–8 Gy with at least five dose levels; colonies ≥ 50 cells.
   - Normalise to the dose-0 plating efficiency of the same arm; fit an LQ model.
   - Primary endpoint: a dose-modifying factor.
2. **Normal human cells matched to the tumour comparators.** At minimum, normal human dermal fibroblasts. All arms run in the same experiments under the same protocol.
3. **Full control set.**
   - vehicle;
   - a cell-free extract-only interference control;
   - sham irradiation;
   - positive controls.
4. **Independent biological replicates.**
   - At least three, on separate days, passages and irradiation sessions.
   - Randomise dose across plates (never one dose per plate) and record plate as a blocking factor.
5. **Schedule × concentration design.**
   - Extract given before, during and after irradiation, with a washout arm.
   - Concentrations stated in one unit.
6. **Chemical characterisation of the extracts.**
   - Voucher specimen, protocol, yield, storage and a chromatographic fingerprint.
   - Until this exists, **no composition may be stated or implied**.
7. **Orthogonal readouts, kept as covariates.**
   - γH2AX/53BP1 foci kinetics after 2 Gy;
   - cell-cycle distribution;
   - plating efficiency.
8. **Pre-specification.** Primary endpoint, sample size, a mixed model with plate and experiment as random effects, and the multiplicity plan, all registered before data collection.
9. **If proliferation itself is of interest,** measure it as its own endpoint under its own `endpoint_class`.

## 8. Permitted and forbidden wording (binding for the manuscript)

**Use:**
- "motivated by";
- "post-irradiation proliferative response";
- "apparently normal hamster fibroblasts (V79)";
- "hypothesis-generating";
- "associated with mSF2";
- "attribution stability";
- "requires experimental testing";
- "two of the three cell lines used in the motivating experiment are represented in the public resource".

**Avoid:**
- "Moringa radioprotects normal cells";
- "selective radioprotection" as a finding;
- "validated by the Moringa data";
- "radioresistance" or "radiosensitivity" for a PEF;
- "mechanism" for a feature attribution;
- PEF and SF2 used interchangeably or on one axis;
- any extract concentration quoted without the unit caveat;
- "murine" for V79.

## 9. Checks performed and not performed

**Performed:**
- read `docs/moringa_scientific_linkage.md`, the CLARIFi manifest and `docs/data_management.md`;
- verified the citations (2026-10-21);
- checked identifier presence in CLARIFi;
- Cellosaurus accession lookups (curator).

**Not performed:**
- reading any mSF2 value;
- ICLAC lookup;
- confirming the DepMap release;
- model runs;
- downloads;
- a literature search on *M. oleifera* phytochemistry. This was deliberate: it risks importing composition claims that the manuscript does not support. (The literature-reviewer's search for the manuscript's publication record is reported in `docs/phase_01_literature_review.md` Part B.)

**The scanned PDF was not re-opened in this pass.** Manuscript statements come from the extraction verified against the page images on 2026-10-20.

## 10. Unresolved blockers

1. The CLARIFi licence conflict. Do not redistribute `data/raw/CLARIFi.csv`.
2. The Moringa manuscript has no authors, DOI, journal or reference list. It can only be described as an unpublished motivating study, with the investigator's authorisation.
3. Identity of MCF-7 and DU145 on the Moringa side rests on name alone; the ICLAC lookup is outstanding.
4. The contradiction between positive *A*_D and negative ΔOD. Request the missing pages or raw data from the original authors.
