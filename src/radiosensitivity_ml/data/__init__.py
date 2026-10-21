"""Data acquisition, parsing, identifier harmonisation and provenance.

Implemented (phase_01, descriptive identifier QC only; see docs/phase_01_remediation_report.md):
- ``provenance``: hashing, manifest look-ups, write-once output folders;
- ``cellosaurus``: parsing and verification of saved Cellosaurus API responses;
- ``qc_identifiers``: deterministic CLARIFi -> DepMap -> Cellosaurus identity matching;
- ``components``: relationship groups (connected components);
- ``eligibility``: pre-fixed eligibility rules and feasibility quantities;
- ``qc_report``: assembly and deterministic writing of the QC tables.
``identifiers`` remains a phase_03 placeholder.

Raw files under data/raw/ are read-only inputs. Nothing in this subpackage may
modify them. Every endpoint class (clonogenic SF, profiling-derived survival,
viability, crystal-violet or optical-density proliferation, gene expression) is
kept in its own table.
"""
