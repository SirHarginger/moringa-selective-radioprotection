# Graph Report - moringa-selective-radioprotection  (2026-08-26)

## Corpus Check
- Corpus is ~6,070 words - fits in a single context window. You may not need a graph.

## Summary
- 226 nodes · 401 edges · 26 communities (23 shown, 3 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 11 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- NCI Data Acquisition
- Raw Activity Audit
- Exploratory Analysis Plots
- Analysis Configuration
- Chemistry Preparation Tests
- Reconstruction Regression Tests
- NCI Preparation Script
- Project Package Metadata
- Project README
- Dependency Requirements

## God Nodes (most connected - your core abstractions)
1. `Moringa-Rad Conda Environment` - 18 edges
2. `prepare_raw_activity_table()` - 14 edges
3. `main()` - 13 edges
4. `main()` - 13 edges
5. `prepare_nci_stage()` - 13 edges
6. `evaluate_resource()` - 11 edges
7. `_build_raw_zscore_reconstruction()` - 11 edges
8. `write_outputs()` - 10 edges
9. `load_project_config()` - 9 edges
10. `clean_nsc_id()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `load_project_config()`  [EXTRACTED]
  scripts/analyze_nci.py → src/moringa_radioprotection/nci.py
- `main()` --calls--> `load_project_config()`  [EXTRACTED]
  scripts/audit_nci_raw.py → src/moringa_radioprotection/nci.py
- `evaluate_resource()` --calls--> `timestamp_utc()`  [EXTRACTED]
  scripts/fetch_nci.py → src/moringa_radioprotection/nci.py
- `main()` --calls--> `load_project_config()`  [EXTRACTED]
  scripts/prepare_nci.py → src/moringa_radioprotection/nci.py
- `main()` --calls--> `prepare_nci_stage()`  [EXTRACTED]
  scripts/prepare_nci.py → src/moringa_radioprotection/nci.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **NCI-60 Cell-Line Modeling Inputs** — config_analysis_dtp_nci60_zscore, config_analysis_mcf7, config_analysis_du145 [EXTRACTED 1.00]

## Communities (26 total, 3 thin omitted)

### Community 0 - "NCI Data Acquisition"
Cohesion: 0.08
Nodes (54): build_rows(), configure_logger(), evaluate_resource(), main(), Logger, Path, Check for presence, download if needed, and validate the resource., acquisition_requirements() (+46 more)

### Community 1 - "Raw Activity Audit"
Cohesion: 0.08
Nodes (51): configure_logger(), main(), Logger, Path, clean_nsc_id(), Normalize the original NSC identifier while preserving its source format., _boundary_counts(), build_boundary_value_audit() (+43 more)

### Community 2 - "Exploratory Analysis Plots"
Cohesion: 0.09
Nodes (39): configure_logger(), main(), plot_response_difference_distribution(), plot_response_distribution(), plot_response_scatter(), plot_scaffold_frequency(), DataFrame, Logger (+31 more)

### Community 3 - "Analysis Configuration"
Cohesion: 0.07
Nodes (32): Moringa Selective Radioprotection Analysis Configuration, COCONUT Screening Library, DTP NCI-60 Raw Replicate Activity Dataset, DTP NCI-60 Processed Z-Score Dataset, DU145 Cancer Cell Line, MCF-7 Cancer Cell Line, Morgan Molecular Fingerprint, NCI-60 Compound-Response Dataset (+24 more)

### Community 4 - "Chemistry Preparation Tests"
Cohesion: 0.22
Nodes (11): canonicalize_smiles(), normalize_smiles_value(), parse_numeric_response(), Any, Trim and normalize missing SMILES strings while preserving original content., Parse a SMILES string and return validity, canonical SMILES, and InChIKey., Coerce CellMiner response strings to numeric values, treating missing labels as…, test_invalid_smiles_returns_false() (+3 more)

### Community 5 - "Reconstruction Regression Tests"
Cohesion: 0.67
Nodes (5): _processed_frame(), DataFrame, _raw_profile_frame(), test_zscore_reconstruction_summary_has_one_row_per_target_and_ddof(), test_zscore_reconstruction_treats_na_as_missing()

### Community 6 - "NCI Preparation Script"
Cohesion: 0.60
Nodes (4): configure_logger(), main(), Logger, Path

## Knowledge Gaps
- **20 isolated node(s):** `moringa-selective-radioprotection`, `README`, `COCONUT Screening Library`, `PubChem Standard Identifiers`, `conda-forge` (+15 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `Exploratory Analysis Plots` to `NCI Data Acquisition`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Why does `load_project_config()` connect `NCI Data Acquisition` to `Raw Activity Audit`, `Exploratory Analysis Plots`, `NCI Preparation Script`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Why does `main()` connect `Raw Activity Audit` to `NCI Data Acquisition`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **What connects `moringa-selective-radioprotection`, `README`, `COCONUT Screening Library` to the rest of the system?**
  _20 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `NCI Data Acquisition` be split into smaller, more focused modules?**
  _Cohesion score 0.07727272727272727 - nodes in this community are weakly interconnected._
- **Should `Raw Activity Audit` be split into smaller, more focused modules?**
  _Cohesion score 0.07910014513788098 - nodes in this community are weakly interconnected._
- **Should `Exploratory Analysis Plots` be split into smaller, more focused modules?**
  _Cohesion score 0.09175377468060394 - nodes in this community are weakly interconnected._