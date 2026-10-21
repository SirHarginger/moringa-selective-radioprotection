# Data management

Status: phase_00. **Claude Code has not downloaded any dataset.** One file, `data/raw/CLARIFi.csv`, was placed by the investigator. Its metadata have been verified against the published record (§8).

## 1. Directory purposes

| Folder | Contents | Git |
|---|---|---|
| `data/raw/<source_slug>/<release_tag>/` | Source files exactly as received; write-once | Ignored |
| `data/interim/` | Parsed and harmonised tables, one per endpoint class | Ignored |
| `data/processed/` | Analysis-ready tables, each with a run record | Ignored |
| `data/manifests/` | Provenance records (YAML), one per source and release | **Tracked** |
| `docs/datasets/` (phase_01) | Human-readable dataset cards linking to manifests | Tracked |

Folder names use lowercase snake case, for example `data/raw/depmap/<release>/`. If the release is unknown, use `unverified_<YYYYMMDD received>`. Never guess a release tag.

## 2. Provenance requirements

Every raw file needs a manifest entry (schema: `data/manifests/_template.yaml`) **before** any code reads it. Required fields:

- source name, publication DOI, data DOI or accession, landing and file URLs;
- release/version, release date, licence (SPDX where available) and whether redistribution is allowed;
- access date (ISO 8601), who retrieved it, retrieval method;
- per file: SHA256, size, format, encoding, delimiter, line count, header, column meanings, identifier namespaces, units;
- endpoint class, definition, assay, dose (Gy), radiation type, time point, replicate structure;
- known missingness, ordered transformations, inclusion and exclusion rules, reviewer;
- `provenance_status`: `unverified` until a named person has checked source, licence and endpoint meaning.

Download code is written only after the source has been verified, and is run only with the investigator's permission.

## 3. Versioning and checksums

- Every raw folder gets a `SHA256SUMS` file. Loaders verify checksums against the manifest and stop on any mismatch.
- Outputs in `data/interim/`, `data/processed/` and `results/` each get a JSON run record:
  - git commit, plus a dirty-tree flag (runs refuse a dirty tree);
  - config path and SHA256, random seeds, lockfile hash;
  - SHA256 of every input and output;
  - command, UTC timestamps, OS.
- DVC or a similar tool may be proposed later. It is not installed.

## 4. Cell-line identity

- **Canonical key:** the Cellosaurus accession (`CVCL_xxxx`). A cell-line RRID is `RRID:CVCL_xxxx`, the same accession. The Cellosaurus release used must be recorded.
- **Keep originals:** source identifiers (DepMap `ACH-` model IDs, CCLE names, COSMIC/Sanger IDs and others) are kept unchanged alongside the canonical key.
- **Alias table:** versioned and tracked. It holds normalised names (case, punctuation, hyphens), synonyms and parent/derived relationships.
- **Flag and exclude until a human resolves them:**
  - ambiguous or one-to-many matches;
  - lines on the ICLAC misidentified register (record its version);
  - lines Cellosaurus marks as problematic;
  - same-donor and derived lines (these must share a split group).
- **Before any split:**
  - build within- and cross-dataset overlap tables on the canonical key;
  - report duplicates;
  - split by cell line (plus donor, lineage or dataset group as the protocol specifies).
- The exact identifier columns each source release ships are **to be verified in phase_01**.

## 5. Keeping endpoints separate

Every table has a required `endpoint_class` from a fixed list:

`clonogenic_sf` · `profiling_derived_survival` · `model_derived` · `viability` · `proliferation_crystal_violet` · `proliferation_optical_density` · `gene_expression` · `unknown`

- Each class has its own long-format table with columns `cell_id_cvcl, source, release, endpoint_class, assay, dose_gy, value, unit, replicate info`.
- No column mixes classes. Values are never rescaled or harmonised silently.
- Joins across classes, or across sources within a class, must be named in config, justified in the protocol and logged in the manifest's `transformations`.
- A schema check (tool to be proposed in phase_03, not installed) fails on any unannotated mix.
- Rows with `unknown` cannot be used for modelling.

## 6. Raw data rules

- Never edit, overwrite, rename or re-encode files in `data/raw/`.
- Corrections go into code as documented transformations, with the reason recorded.
- No invented data. No silent imputation.

## 7. Missing observations

- Record missingness per source and column in the manifest (`known_missingness`).
- Missing values stay missing in `interim/`. Any imputation must be prespecified in the protocol and performed inside training folds only.
- Report the number of cell lines excluded at each step (a flow table for the manuscript).

## 8. Current dataset: CLARIFi (`data/raw/CLARIFi.csv`)

Manifest: `data/manifests/clarifi__v1_0.yaml`. Checksum results: `docs/phase_00_verification.md` §7.

**Verified from the published record** (Zenodo 10.5281/zenodo.20710748; Oike et al., *Cancer Science* 116(3):690–697, DOI 10.1111/cas.16334):
- CLARIFi contains **literature-derived clonogenic radiosensitivity measurements**.
- `mSF2` is the median, per cell line, of published SF2 values: survival fraction after 2 Gy photon irradiation, assessed by clonogenic assays.
- The record covers 285 cell lines from 28 cancer types. The local file has 285 data rows plus a header. Its last line has no trailing newline, so `wc -l` reports one line fewer.
- Identifiers are DepMap model IDs and CCLE names taken from the DepMap portal, as stated in the paper.

**Still unresolved:**
- Licence: the dataset (Zenodo) is declared CC BY 4.0 and the article CC BY-NC 4.0. Neither source settles the other. Redistribution is **unresolved**; apply the stricter terms (attribution, non-commercial) and do not redistribute until the authors confirm. Details are in the manifest's `licences` block.
- How the median was formed, and how many values contribute per cell line.
- The DepMap release behind the IDs (the paper gives only a portal access date of 1 December 2023).
- Whether the Zenodo record was uploaded by the authors.
- Because CLARIFi is aggregated from many publications, the source study and lab are potential confounders. They must be documented per record in phase_01.

The values in the file have not been analysed.

## 9. Source manuscripts

- Location: `references/source_manuscripts/`. PDFs there are gitignored because redistribution is not authorised.
- Their SHA-256 and MD5 checksums, size, provenance and access date are recorded in the tracked `references/source_manuscripts/manifest.yaml`.

## 10. Licences and redistribution

- Record the licence and terms URL per source. Default assumption: **do not redistribute** raw or derived data until the licence is confirmed.
- Manifests, code and documentation are tracked and may be shared. Raw data are not committed.
- Any publication data package includes only what each licence permits, with citations to the original sources.
