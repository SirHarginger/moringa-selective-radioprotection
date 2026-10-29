# Compound evidence: curation record, searches and unresolved gaps

**What this is.** The audit trail for `data/compounds/moringa_constituents.yaml` and
`data/compounds/compound_biology_evidence.yaml`. Curated 2026-10-22 by the
`literature-reviewer` agent (searching and reading only; no code was run, no files were
written by the agent), recorded by Claude Code. Scoring rules: `docs/compound_protocol.md`.

**Verification.** Every DOI was checked against the Europe PMC REST API or the Crossref
API, and the route is recorded per record (`doi_verified_via`). Every PubChem CID and
InChIKey was fetched from PubChem PUG-REST during curation. `reading_depth` records
whether the abstract or the full text was read. Nothing unverifiable was recorded as fact.

---

## 1. The headline finding

**Only one constituent has a structurally confirmed identification in a dichloromethane
fraction of Moringa seed *and* leaf: niazimicin.** Abdelsayed, Abdel Motaal and Hanafi
(*J Food Drug Anal* 2021;29(1):128-143, DOI 10.38212/2224-6614.3282, PMID 35696224,
full text read) isolated the reference standard from the **seed methylene-chloride
fraction** of a 70% ethanol maceration, confirmed it by HRMS, UV, IR, EI-MS and 1D/2D NMR,
and quantified it by validated UPLC-MS/MS (MRM 358 → 107) in both the seed and the leaf
CH₂Cl₂ fractions. The same work did **not** identify niazirin or glucomoringin there.

The only other dichloromethane-specific identifications are GC-MS library matches in leaf
DCM material, all read at abstract level: 4-hydroxyphenylacetonitrile and methyl
4-hydroxyphenylacetate (Mohd Fisall et al. 2021), palmitic acid and cis-vaccenic acid
(Khandelwal and Khurana 2019).

**Consequence for the project.** The compound with the best claim to presence in the
extraction solvent actually used has, separately, **no** purified-compound radiation
biology; the compounds with radiation evidence have never been verified in a DCM extract.
This tension is the central honest result of the module and is reported as such.

## 2. Studies of dichloromethane extracts of seed or leaf

| # | Study | Part | What was identified |
|---|---|---|---|
| 1 | Abdelsayed 2021, *J Food Drug Anal* [FT] | seed + leaf | **Niazimicin**, isolated from the seed CH₂Cl₂ fraction, NMR/HRMS confirmed, UPLC-MS/MS quantified in seed and leaf CH₂Cl₂ fractions. Niazirin and glucomoringin not found |
| 2 | Abdelsayed 2021, *J Food Biochem* [ABS] | seed | Methylene-chloride and ethyl-acetate fractions "contain" niazimicin. **Same group as #1**, so not independent |
| 3 | Mohd Fisall 2021, *Mol Biol Rep* [ABS] | leaf | DCM fraction of a methanolic extract; GC-MS major compounds 4-hydroxybenzeneacetonitrile and methyl 4-hydroxyphenylacetate. Selective against MCF-7 relative to MCF 10A. Full compound list and identification criteria **not accessible** (paywalled) |
| 4 | Khandelwal & Khurana 2019, *Medicinal Plants* 11(1) [ABS via Crossref] | leaf | DCM extract; GC-MS reported 96 compounds; named: n-hexadecanoic acid (28.35%), cis-vaccenic acid (10.68%). **No PMID; journal not indexed in PubMed or Europe PMC**; full list and method inaccessible |
| 5 | Adebayo 2017, *AJTCAM* [FT] | seed | DCM fraction of an 80% ethanol extract (IC₅₀ 26 µg/mL on MCF-7, but similar inhibition of MCF 10A, so **not** selective). Chemistry: only "hexadecanoic acid … in the samples" by GC-MS, not assigned to a fraction, no method described |
| 6 | Adebayo 2018, *Pharmacogn Mag* [FT] | seed | A DCM fraction was prepared but its results were not reported; GC-MS covered only the polar extracts |
| 7 | Banoub 2026, *Sci Rep* [FT] | leaf | Methylene-chloride fraction prepared, but GC-MS was run on the hexane fraction only. Its sentence about an Indian DCM extract rich in palmitic and cis-vaccenic acid cites an **unrelated reference** (a soil-PAH paper), so that citation is unsupported |
| 8 | Matsuoka 2022, *Food Sci Nutr* [FT] | leaf | CH₂Cl₂ extract; NMR on a subfraction was too impure for identification, so **no compounds were identified**. Its "possibly yes" for chlorogenic acid is speculation and is **not** treated as evidence |
| 9 | Futagbi 2026, bioRxiv [ABS] | seed | DCM fraction tested for antibacterial activity only; no chemistry. **Preprint** |
| 10 | Faizi 2014, *Asian Pac J Trop Biomed* [ABS] | **root** | Root DCM extract, 63 compounds by GC/GC-MS. **Wrong plant part**; excluded |

CH₂Cl₂ used only as a chromatography eluent (Jiang 2023; Li 2023) does not make a
dichloromethane extract and was not counted.

## 3. Compounds whose identification is weak or absent, and why it matters

**Correction, 2026-10-22.** An earlier version of this section listed quercetin and
kaempferol as "cannot be ranked". That was wrong, and it was an *unsupported exclusion*
rather than an application of the rubric: both have primary (non-review) seed or leaf
reports, so under the prespecified D1 rule they score 1 — the weakest identification band,
for a spectral-library or dereplication match — not 0. Only a compound with **no** primary
seed or leaf report is not assessable, which is why benzyl isothiocyanate (roots only) is
excluded and the aglycones are not. The rubric was **not** changed; the prose was. The
practical consequence is that the aglycones appear in the ranked table with a visible
identity caveat, and their extraction category (`indirect_or_unconfirmed`) is displayed
beside the score rather than folded into it.

| Compound | Identification status | Consequence |
|---|---|---|
| **Quercetin**, **kaempferol** (free aglycones) | Tentative LC-HRMS dereplication only (Shady 2022, solvent not stated) and a leaf table without an authentic standard. The free aglycone may also form by hydrolysis of the abundant glycosides during extraction. The forms primary analytical work actually establishes in leaf are the **glycosides** (isoquercitrin, astragalin, rutin) | **Assessable at D1 = 1**, not excluded. These carry the **strongest radiation evidence of any compound considered** (quercetin: 6 independent groups, both directions; kaempferol: 2 groups), so the weak identification — not a missing identification — is the consequential gap. Aglycone evidence must not be transferred to a glycoside, or the reverse, without pharmacokinetic justification |
| **Benzyl isothiocyanate** | Bennett 2003 reports its precursor, benzyl glucosinolate, in **roots only**; seed and leaf carry the rhamnosyloxy-benzyl glucosinolate instead. Studies using BITC with Moringa employ it as a purchased test compound | The most consistent radiosensitisation evidence in the set (two independent groups, concordant, with a G2/M checkpoint mechanism), and the basis of the class analogy to moringin — which earns no points by design |
| **Gallic acid**, **caffeic acid** | No primary report of either in *M. oleifera* seed or leaf was located | Both have substantial normal-tissue radioprotection evidence (gallic acid uniquely via homologous-recombination repair and TLK1). They are absent from the inventory, so no evidence was recorded for them |
| **Glucomoringin**, **isoquercitrin** | Documented constituents, but no primary radiation or process evidence located | Ranked on identity alone |
| **Niazimicin** | The one neuroprotection study dosed a **70% ethanol seed-extract fraction at 250 mg/kg**, not the purified compound; caspase-3 and iNOS appear only in docking | Recorded with `counts_for_score: false`, so the absence of purified-niazimicin biology is explicit rather than invisible |

## 4. Direction of effect: what the evidence actually says

Radioprotection and radiosensitisation were never merged, and the cell type is always
recorded. Two findings deserve emphasis:

- **Chlorogenic acid carries a liability.** Yin et al. (2022) report that it *protects
  hepatocellular carcinoma cells* from radiation via NRF2, concluding it "could hinder the
  therapeutic effect of radiotherapy". This must never be pooled with the normal-tissue
  chlorogenic-acid protection studies (bone marrow, testis). Under the prespecified rule it
  caps the tier at C.
- **Astragalin carries a liability.** Its only DDR-relevant primary signal is
  *pro-genotoxic* (DNA adducts and repairable DNA damage in yeast and cell-free systems).
  The one astragalin "radiation" paper is **UVB**, which is not ionising radiation.

Informative negatives were kept: George, Lunec and Cramp (1983) found membrane oleate
enrichment did **not** alter clonogenic radiosensitivity of human lymphoid cells.

Quercetin (Citrin group, 2013) is the best published model of how a selectivity claim must
be worded: normal-tissue anti-fibrotic protection **with no effect** on fibroblast or
murine tumour radioresponse.

## 5. Excluded on principle

- **UV is not ionising radiation.** A large fraction of hits for quercetin, kaempferol,
  rutin, caffeic acid, astragalin and oleic acid are UVA/UVB photoprotection studies; all
  were excluded from radiation evidence.
- **Carrier-confounded formulations**: quercetin-titanate, quercetin-MOF,
  quercetin-magnetite, gallic-acid-gold, gallic-acid-AgNP, kaempferol-ZIF-8.
- **Different chemical entities**: CAPE (≠ caffeic acid), α-tocopherol succinate
  (≠ α-tocopherol), nitro-oleic acid (≠ oleic acid), allyl isothiocyanate (not a
  documented Moringa constituent).
- **Multi-agent studies** that cannot attribute an effect to one compound: all
  podophyllotoxin + rutin papers; pentoxifylline + tocopherol papers.
- **Retracted work**: Giacoppo et al. 2017 (PMID 28705212) is flagged retracted in Europe
  PMC and is excluded.
- **Unusual design flagged, not counted as radiation evidence**: Patra et al. 2020 tested
  *gamma-irradiated gallic acid* (the drug was irradiated, then applied; the cells were not
  co-irradiated).

## 6. Identifier problems found and resolved

| Compound | Problem | Resolution |
|---|---|---|
| Niazimicin | Name search returns CID 5471459 with **no stereochemistry** | Use **CID 10247749** (defined α-L-rhamnopyranosyl). The (E) thiocarbamate geometry remains a caveat |
| O-Ethyl-4-(α-L-rhamnosyloxy)benzyl carbamate | Name search returns CID 129712240, a **mis-structured record** (C16H23NO8, ethoxy on the sugar) | Use **CID 101942512** |
| Niaziminin | CID 44559760 "Niaziminin A" (C19H25NO7S) holds a structure that **does not match** the thiocarbamate | Use **CID 10023860**; A/B isomer stereochemistry unresolved in PubChem |
| Glucomoringin | **Every** record is a potassium salt with a *different* stereo-InChIKey (CIDs 162639104, 23669698, 177924937); no neutral or anionic record found | **Unresolved.** CID 162639104 recorded with an explicit `identity_caveat`; the investigator must confirm the stereo assignment before publication |
| Moringin | Several stereo variants (CIDs 12002975, 44198764, 14865502) | Use **CID 153557** |
| Acetyl-rhamnosyloxybenzyl ITC | Positional isomers have separate records (2'-, 3'-O-acetyl) | Position must be stated whenever cited |
| cis-Vaccenic acid | EI-MS library matching cannot distinguish C18:1 positional isomers (Δ9 oleic vs Δ11 vaccenic) without standards | Recorded as **identity uncertain** |
| Flavonol glycosides | LC-MS cannot separate glucoside from galactoside without a standard | Recorded as a caveat on isoquercitrin and astragalin |

## 7. Searches performed

**Constituent curation.** Europe PMC: `"Moringa oleifera" AND dichloromethane` (342 hits,
first 100 screened); `"Moringa" AND ("methylene chloride" OR "CH2Cl2")` (82);
`"Moringa oleifera" AND (dichloromethane OR "methylene chloride") AND ("GC-MS" OR "GC/MS"
OR "gas chromatography" OR "LC-MS" OR NMR)` (183, 99 screened); seed + DCM + (isolat* OR
NMR); author searches for Faizi S, Bennett RN, Guevara AP, Murakami A; niaziminin and
"rhamnosyloxy" queries; glucosinolate/isothiocyanate profiling 2003-2016; leaf phenolics
(chlorogenic acid, isoquercitrin, astragalin); tocopherol and sterol queries. Crossref:
bibliographic query for Moringa DCM GC-MS (40 rows) plus single-DOI lookups. PubChem
PUG-REST: name lookups, 2D-similarity lookups, same-connectivity lookup, property fetches
for every CID recorded. One web search for leaf DCM GC-MS phytol.

**Biology curation.** Europe PMC title-and-abstract queries per compound, sorted by
citation count, combining the compound name with radiation, irradiation, radioprotective,
radiosensitising and radiation-induced; plus process queries (apoptosis, Nrf2, cell cycle,
DNA, oxidative, p53). Reported hit counts: quercetin 77, rutin 66, caffeic acid 31,
tocopherol 31, gallic acid 24, oleic acid 22, chlorogenic acid 14, phytol 11, isothiocyanate
7, kaempferol 7, β-sitosterol 2, moringin + radiation 0. Record-level `EXT_ID` retrievals
for every item extracted. Crossref cross-checks for three DOIs
(10.3892/or.2015.4204; 10.1016/j.freeradbiomed.2015.12.029; 10.1155/2022/4566949).

## 8. Unresolved gaps the investigator must close before publication

1. **Glucomoringin identifier ambiguity** (section 6) — unresolved.
2. **Full texts not obtained**: Bennett 2003, Amaglo 2010, Faizi 1994/1995, Guevara 1999,
   Murakami 1998 (paywalled); Mohd Fisall 2021 (Springer auth redirect); Khandelwal 2019
   (not indexed, full list of 96 compounds inaccessible); Waterman 2014, Vats 2017 (fetch
   failed). Their extraction solvents and identification criteria remain unverified beyond
   the abstracts, which is why several records carry `identification_strength: not_stated`.
3. **Radiation doses and concentrations missing from abstracts** and required before the
   evidence table is published: radiation dose for QUE-01, QUE-02, KAE-01, CGA-01, BST-01,
   OLE-01; concentration for QUE-01, QUE-02, KAE-01, KAE-02, CGA-01, BST-01, MOR-04,
   NZR-01; cell-line identity for QUE-01 and CGA-01.
4. **β-Sitosterol radiation modality (BST-01)** is ambiguous ("ion irradiation, 6 Gy" as
   rendered); confirm gamma versus heavy ion from the full text.
5. **Erratum and retraction checks**: read the Heliyon erratum for CGA-03 (PMID 37151639);
   re-verify the retraction status of CGA-01 immediately before submission.
6. **Gene lists are deliberately incomplete.** Only symbols a paper actually reports as
   measured are recorded. KAE-01 names pathways but no individual proteins, so its gene
   list is empty; several studies measured no genes at all and their lists must stay empty
   rather than be back-filled from reviews.
7. **Glycoside/aglycone pharmacokinetics.** Isoquercitrin, astragalin and rutin are
   extensively deglycosylated in vivo. Aglycone evidence must not be transferred to the
   glycoside, or the reverse, without explicit pharmacokinetic justification.
8. **Group independence.** True independent-group counts are lower than raw paper counts:
   Iori (compound supplier) links most moringin studies; Abdelsayed/Hanafi links both
   niazimicin papers; Arsad links both 4-hydroxyphenylacetonitrile reports;
   Bennett/Mellon links Bennett 2003 and Amaglo 2010; Raskin links Waterman 2014 and Tumer
   2015; Thabet/Abdel-Rafei links rutin RUT-02 and β-sitosterol BST-02. The scoring code
   deduplicates by `research_group` for exactly this reason.
9. **Not searched**: PubMed-native MeSH strategies (e.g. `Radiation-Protective
   Agents[MeSH]`); heavy-ion and proton-specific searches; non-English literature. Two
   located abstracts were not extracted: Yao 2025 caffeic acid/NRF2 (PMID 40174789) and
   Hosseinimehr 2008 chlorogenic acid (PMID 18389093).

*No code was executed and no analysis was run during curation, consistent with the
project's hard rule.*
