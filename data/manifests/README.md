# data/manifests/

Tracked provenance records for every file in `data/raw/`. The raw data files are gitignored; these manifests are not.

- One manifest per source and release: `<source_slug>__<release>.yaml` (e.g. `clarifi__v1_0.yaml`). If the release is unknown, use `<source_slug>__unverified_<YYYYMMDD received>.yaml`.
- Use `_template.yaml` as the schema. When a value is unknown, leave it `null`. Never guess.
- Only files whose `provenance_status` is `verified` may be used for modelling.
- Full rules: `docs/data_management.md`.

Current manifests:

| Manifest | File | Status |
|---|---|---|
| `clarifi__v1_0.yaml` | `data/raw/CLARIFi.csv` | **unverified** since 2026-10-21 (licence conflict CC-BY-4.0 vs CC-BY-NC-4.0 unresolved; no named reviewer). Integrity verified: local MD5 matches Zenodo |
| `depmap__24q4.yaml` | `data/raw/depmap/24q4/` | unverified; metadata verified; **not acquired** |
| `depmap__23q4_v1.yaml` | `data/raw/depmap/23q4_v1/Model.csv` | unverified; identity audit only; **not acquired** |
| `yard2016__ncomms11428_v1.yaml` | `data/raw/yard2016/ncomms11428_v1/` | unverified; supplement layout unverified; **not acquired** |
| `cellosaurus__r56_0.yaml` | `data/raw/cellosaurus/r56_0/` | unverified; API responses **not yet saved** |
| `geo_gse184119__suppl_20210925.yaml` | `data/raw/geo_gse184119/suppl_20210925/` | unverified; optional context only; **not acquired** |
| `iclac__v14.yaml` | `data/raw/iclac/v14/` | unverified; optional lookup; **not acquired** |

Phase_01 manifests also use these optional fields (not yet in `_template.yaml`): `published_md5`, `published_size_bytes`, `local_md5`, `expected_size_bytes`, `displayed_size`, `columns_of_interest`, `purpose`, `queries`, `publication`, `licences`, `licence_source`, `licence_terms_applied`, `integrity_status`, `metadata_verified_date`.
