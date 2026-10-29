# LaTeX edition of the French Embassy report

## Which source is authoritative

**`reports/french_embassy/report.md` is the only place where the report text is written.**
The LaTeX edition is generated from it on every build; there is no second copy of the
narrative to keep in step. The same holds for the other inputs:

| Content | Authoritative source | How it reaches the PDF |
|---|---|---|
| Report text, headings, inline tables, citations | `../report.md` | pandoc + `filters/report.lua` -> `generated/{summary,main,appendices}.tex` |
| Title, subtitle, date, author block | YAML header of `../report.md` | `filters/report.lua` -> `generated/metadata.tex` |
| Figures (numbers, files, captions) | `../figure_manifest.csv` and `figures/pdf/*.pdf` | vector PDFs included unchanged; the build checks every caption in `report.md` against the manifest |
| Result tables 1-3, S1-S4, C1-C4, R1-R3 | CSV files named in `../table_manifest.csv`; captions from `results/tables/primary_v1/publication_v1/captions.md` | `filters/datatables.lua` reads the CSVs at build time -> `generated/data_tables.tex` (Appendix H) |
| References | `../references.bib` | biblatex + biber; only cited entries are printed; the internal `note` fields are not printed |
| Layout (fonts, colours, cover, headers, table style) | `main.tex`, `cover.tex`, `embassy-report.sty`, `filters/table_specs.lua` | hand-maintained, presentation only |

Files in `generated/` and `build/` are build products: never edit them. To change the text,
edit `report.md`; to change a figure, re-render it with `scripts/make_report_figures.py`;
to change how a result table is laid out, edit `filters/table_specs.lua`.

## Build

From the repository root:

```bash
bash reports/french_embassy/latex/build.sh            # incremental
bash reports/french_embassy/latex/build.sh --clean    # from scratch
```

Output: `reports/french_embassy/outputs/final_project_report_latex.pdf`. The pandoc
PDF/DOCX build (`../build.sh`) is separate and unaffected.

Requirements: pandoc >= 3.1, LuaLaTeX, latexmk, biber, and the fonts Linux Libertine O,
Linux Biolinum O and DejaVu. The build runs no model, analysis or ranking; it reads saved
outputs only.

Steps: (1) `report.md` is converted in four parts; (2) the result CSVs are typeset;
(3) SHA-256 checksums of every input, the git commit and the pandoc version are recorded
(Appendix I and the document-information page); (4) `latexmk` runs LuaLaTeX and biber
until cross-references settle. `SOURCE_DATE_EPOCH` defaults to the modification time of
`report.md`, so rebuilding unchanged inputs gives the same document.

## What makes the build fail

The PDF is copied to `outputs/` only if every check passes. The build stops with a
message naming the problem when:

- pandoc, LuaLaTeX, latexmk or biber is missing, or a LaTeX package or font is missing;
- a figure in `report.md` is absent from `figure_manifest.csv`, or the reverse; a figure
  number or caption differs from the manifest; figures are out of numbering order;
- a table in `table_manifest.csv` has no layout in `table_specs.lua`, is not marked
  `generated`, its CSV is missing, a shown column is missing, a numeric column holds a
  non-number, or a column declared constant is not;
- a Markdown table has no caption, or "Figure N", "Table X" or "§N" in the text has no
  target;
- a citation or cross-reference is undefined, biber reports an error, a character is
  missing from every font, a float is too large for the page, or labels did not settle;
- any figure, table, chapter or appendix ends up with a number different from the one
  `report.md` uses (checked against `build/main.aux`).

Overfull lines, biber warnings and remaining `[TO BE COMPLETED]` fields are reported but
do not stop the build.

## Layout decisions

- KOMA-Script `scrbook`, one-sided A4, 11 pt Linux Libertine O with Linux Biolinum O
  headings; navy accent colour, legible in greyscale.
- Order: cover, document-information page, executive summary (unnumbered, as in
  `report.md`), contents, lists of figures and tables, chapters 1-11, references,
  Appendices A-G (from `report.md`), H (typeset result tables), I (build provenance).
- Figures keep their report numbers (1-9 in the body, S1-S2 in the appendices) and their
  full captions; the List of Figures uses each caption's first sentence.
- Markdown tables are numbered by chapter (Table 2.1, ...) so they cannot be confused with
  the result tables, which keep their project identifiers (Table 1, S2, C3, R1, ...).
- `report.md` uses "§7" for chapter 7; the executive summary is unnumbered so that these
  references stay correct in both the pandoc and the LaTeX builds.
- Wide result tables are set on landscape pages. Rounding, the rows shown, and the source
  columns not shown are stated in each table's note.
