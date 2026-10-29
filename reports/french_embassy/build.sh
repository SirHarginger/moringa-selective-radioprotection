#!/usr/bin/env bash
# Build the French Embassy project report (INVESTIGATOR-RUN).
#
#   bash reports/french_embassy/build.sh            # PDF + DOCX
#   bash reports/french_embassy/build.sh pdf        # PDF only
#   bash reports/french_embassy/build.sh docx       # DOCX only
#
# Run from the repository root. The build FAILS if a referenced figure is missing: a
# report must never be produced with absent figures, so render them first with
#   python scripts/make_report_figures.py --config configs/figures_report.yaml
#
# Requires pandoc, and for PDF a LaTeX engine (xelatex). Both were present on the
# investigator's machine when this script was written (/usr/bin/pandoc, /usr/bin/xelatex).
# Citations are processed by pandoc's built-in citeproc from references.bib.
#
# APA 7 reference style needs apa.csl, which is NOT bundled (it is a third-party file with
# its own licence). Download it once into this folder:
#   curl -L -o reports/french_embassy/apa.csl \
#     https://raw.githubusercontent.com/citation-style-language/styles/master/apa.csl
# Without it, the build proceeds with pandoc's default author-date style and says so.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
OUT="${HERE}/outputs"
SRC="${HERE}/report.md"
TARGET="${1:-all}"

cd "${ROOT}"
mkdir -p "${OUT}"

command -v pandoc >/dev/null 2>&1 || { echo "ERROR: pandoc is not installed." >&2; exit 1; }

# --- every figure the report references must already exist -----------------------------
# Paths come from figure_manifest.csv, whose `png` and `pdf` columns are already
# repository-relative, so no path rewriting is needed. (An earlier version derived them
# from the Markdown by replacing the leading "../../" with "figures/", which produced
# "figures/figures/png/..." and reported every figure as missing.) In the report the same
# files are referenced as ../../figures/png/... , which is correct relative to report.md
# and is what pandoc resolves through --resource-path below.
MANIFEST="${HERE}/figure_manifest.csv"
if [ ! -f "${MANIFEST}" ]; then
  cat >&2 <<'MSG'
ERROR: reports/french_embassy/figure_manifest.csv is absent, so the figures referenced by
the report cannot be verified. Render the figures first:
  python scripts/make_report_figures.py --config configs/figures_report.yaml
MSG
  exit 1
fi

missing=0
while IFS=, read -r _label _id _stem png pdf _meta _prov _caption; do
  [ -n "${png}" ] || continue
  for figure in "${png}" "${pdf}"; do
    [ -n "${figure}" ] || continue
    if [ ! -f "${ROOT}/${figure}" ]; then
      echo "MISSING FIGURE: ${figure}" >&2
      missing=1
    fi
  done
done < <(tail -n +2 "${MANIFEST}")

# Any figure embedded in the report but absent from the manifest would be unverified.
while IFS= read -r embedded; do
  grep -Fq "${embedded}" "${MANIFEST}" || {
    echo "FIGURE NOT IN MANIFEST: ${embedded}" >&2
    missing=1
  }
done < <(grep -o '\.\./\.\./figures/png/[^)]*\.png' "${SRC}" \
          | cut -c7- | sort -u)

if [ "${missing}" -ne 0 ]; then
  cat >&2 <<'MSG'
ERROR: one or more figures referenced by the report are missing or unverified.
Render them first:
  python scripts/make_report_figures.py --config configs/figures_report.yaml
MSG
  exit 1
fi

# --- warn, but do not fail, if a referenced table has not been generated ---------------
if [ -f "${HERE}/table_manifest.csv" ]; then
  while IFS=, read -r _label _id _title path _by status; do
    case "${status}" in
      pending_execution)
        echo "NOTE: ${path} has not been generated (scripts/make_compound_tables.py)." >&2 ;;
    esac
  done < <(tail -n +2 "${HERE}/table_manifest.csv")
fi

CSL_ARGS=()
if [ -f "${HERE}/apa.csl" ]; then
  CSL_ARGS+=(--csl "${HERE}/apa.csl")
else
  echo "NOTE: apa.csl not found; using pandoc's default author-date style." >&2
fi

COMMON=(
  "${SRC}"
  --from=markdown+yaml_metadata_block+implicit_figures+citations
  --citeproc
  --bibliography="${HERE}/references.bib"
  --resource-path="${HERE}:${ROOT}"
  --number-sections
  --toc --toc-depth=2
)

build_pdf() {
  echo "Building ${OUT}/final_project_report.pdf"
  pandoc "${COMMON[@]}" "${CSL_ARGS[@]}" \
    --pdf-engine=xelatex \
    -V documentclass=article -V papersize=a4 -V geometry:margin=25mm \
    -V fontsize=11pt -V linkcolor=black -V urlcolor=blue \
    -o "${OUT}/final_project_report.pdf"
}

build_docx() {
  # Appendix H (the 14 result tables) is generated from the CSV files by the same filter
  # and layout specification as the LaTeX edition, then appended to report.md.
  local tables="${HERE}/latex/generated/data_tables_docx.md"
  mkdir -p "$(dirname "${tables}")"
  pandoc /dev/null --from=markdown --to=markdown \
    --lua-filter="${HERE}/latex/filters/datatables.lua" -M table-format=plain \
    -M table-manifest=reports/french_embassy/table_manifest.csv \
    -M captions-file=results/tables/primary_v1/publication_v1/captions.md \
    -o "${tables}"
  echo "Building ${OUT}/final_project_report.docx"
  pandoc "${COMMON[@]}" "${tables}" "${CSL_ARGS[@]}" \
    -o "${OUT}/final_project_report.docx"
}

case "${TARGET}" in
  pdf)  build_pdf ;;
  docx) build_docx ;;
  all)  build_pdf; build_docx ;;
  *)    echo "usage: build.sh [pdf|docx|all]" >&2; exit 2 ;;
esac

echo "Done. Outputs in ${OUT}/"
