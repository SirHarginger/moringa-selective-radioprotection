#!/usr/bin/env bash
# SUPERSEDED (2026-10-21) by `python scripts/acquire_data.py`, which applies the same rules.
# Kept only for the GEO GSE184119 / ICLAC context downloads (--optional). Do not use it for
# DepMap; the investigator may delete this file once those context sources are no longer needed.
#
# Phase 01 source acquisition (INVESTIGATOR-RUN; Claude Code cannot run curl).
#
# Downloads only the files needed for the phase_01 identifier and feasibility audit.
# File IDs, sizes and published MD5s were verified by the radiogenomics-curator and
# re-confirmed by the reproducibility-auditor (2026-10-21) from
# https://api.figshare.com/v2/articles/27993248 (DepMap 24Q4) and
# https://api.figshare.com/v2/articles/24667905/versions/1 (23Q4 v1).
#
# Behaviour (hardened after software-architect and reproducibility-auditor review):
#   - downloads to <file>.part and checks it (MD5 where published, otherwise file
#     signature) BEFORE renaming, so a bad or HTML "bot check" response never
#     becomes a raw file;
#   - never overwrites an existing file; an existing file is re-checked instead;
#   - files without a published MD5 or signature are rejected if they look like HTML;
#   - each accepted file is made read-only (chmod a-w);
#   - appends one line per download to results/logs/phase_01/acquisition_log.tsv:
#     UTC time, source URL, final URL, HTTP code, size, path, expected MD5, observed MD5,
#     observed SHA-256 -> source for the manifests; kept outside data/raw (immutable);
#   - writes SHA256SUMS once per folder (read-only); later runs VERIFY it and never rewrite it.
# Requires GNU coreutils/findutils (Linux).
#
# Default: ONLY the DepMap 24Q4 core files (one fixed release; ~507 MB in total):
#   README.txt, Model.csv, OmicsProfiles.csv, OmicsDefaultModelProfiles.csv,
#   OmicsExpressionProteinCodingGenesTPMLogp1.csv (uncorrected; provisional primary input).
# Options (each adds files; nothing else of the release is downloaded):
#   --batch-corrected  24Q4 OmicsExpressionProteinCodingGenesTPMLogp1BatchCorrected.csv
#                      (~616 MB; SENSITIVITY option only, separate folder 24q4_sensitivity)
#   --audit-23q4       23Q4 v1 Model.csv (identity drift audit only)
#   --yard             Yard 2016 Supplementary Data 1 and figures (secondary)
#   --optional         GSE184119 and ICLAC v14 (context only)
# Usage, from the repository root:
#   bash scripts/acquire_phase_01.sh
set -euo pipefail

want_yard=false
want_optional=false
want_batch=false
want_23q4=false
for arg in "$@"; do
  case "$arg" in
    --yard) want_yard=true ;;
    --optional) want_optional=true ;;
    --batch-corrected) want_batch=true ;;
    --audit-23q4) want_23q4=true ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

[ -f pyproject.toml ] && [ -d data/manifests ] || { echo "run from the repository root" >&2; exit 2; }

check_md5() {  # check_md5 <file> <md5-or-empty> <hint>
  [ -z "$2" ] && return 0
  echo "$2  $1" | md5sum -c - || { echo "MD5 MISMATCH: $1 ($3)" >&2; exit 1; }
}

check_magic() {  # check_magic <file> <hex-prefix-or-empty>: 504b0304 xlsx/zip, 25504446 pdf, 1f8b gzip
  [ -z "$2" ] && return 0
  local got
  got=$(head -c "$(( ${#2} / 2 ))" "$1" | od -An -tx1 | tr -d ' \n')
  [ "$got" = "$2" ] || { echo "UNEXPECTED CONTENT in $1 (signature $got; HTML block page?)" >&2; exit 1; }
}

check_size() {  # check_size <file> <bytes-or-empty>
  [ -z "$2" ] && return 0
  local got
  got=$(stat -c '%s' "$1")
  [ "$got" = "$2" ] || { echo "SIZE MISMATCH: $1 ($got bytes, expected $2)" >&2; exit 1; }
}

check_not_html() {  # check_not_html <file>: reject HTML error or "bot check" pages
  if head -c 4096 "$1" | grep -qi -e '<html' -e '<!doctype html'; then
    echo "UNEXPECTED HTML in $1 (error or block page?)" >&2; exit 1
  fi
}

LOG=results/logs/phase_01/acquisition_log.tsv   # outside data/raw (raw folders stay immutable)

fetch() {  # fetch <url> <dest> <md5-or-empty> <magic-or-empty> <size-or-empty>
  local url="$1" dest="$2" md5="${3:-}" magic="${4:-}" size="${5:-}"
  mkdir -p "$(dirname "$dest")"
  if [ -e "$dest" ]; then
    echo "exists, not re-downloading: $dest"
    check_md5 "$dest" "$md5" "existing file NOT overwritten; move it aside and re-run"
    check_magic "$dest" "$magic"
    check_size "$dest" "$size"
    return 0
  fi
  echo "downloading: $dest"
  local meta
  meta=$(curl -L --fail --retry 3 --show-error -o "$dest.part" -w '%{url_effective}\t%{http_code}' "$url")
  check_md5 "$dest.part" "$md5" "left as .part; delete it and re-run"
  check_magic "$dest.part" "$magic"
  check_size "$dest.part" "$size"
  check_not_html "$dest.part"
  mv "$dest.part" "$dest"
  chmod a-w "$dest"
  mkdir -p "$(dirname "$LOG")"
  [ -e "$LOG" ] || printf 'utc_time\tsource_url\tfinal_url\thttp_code\tsize_bytes\tpath\texpected_md5\tobserved_md5\tobserved_sha256\n' > "$LOG"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$url" "$meta" \
    "$(stat -c '%s' "$dest")" "$dest" "${md5:-none_published}" \
    "$(md5sum "$dest" | cut -d' ' -f1)" "$(sha256sum "$dest" | cut -d' ' -f1)" >> "$LOG"
}

record_sha256() {  # record_sha256 <dir>: write SHA256SUMS once; on later runs verify it
  if [ -e "$1/SHA256SUMS" ]; then
    (cd "$1" && sha256sum -c SHA256SUMS)
    echo "verified $1/SHA256SUMS (not rewritten; files added later are not listed)"
    return 0
  fi
  (cd "$1" && find . -maxdepth 1 -type f ! -name 'SHA256SUMS*' ! -name '*.part' \
      ! -name 'ACQUISITION_LOG.tsv' -printf '%f\0' \
    | LC_ALL=C sort -z | xargs -0 -r sha256sum > SHA256SUMS.part && mv SHA256SUMS.part SHA256SUMS \
    && chmod a-w SHA256SUMS)
  echo "wrote $1/SHA256SUMS"
}

# --- DepMap Public 24Q4 (CC BY 4.0; DOI 10.25452/figshare.plus.27993248.v1) ---
D=data/raw/depmap/24q4
fetch https://ndownloader.figshare.com/files/51065795 "$D/README.txt"                    54628c15a10b9ff6536db245cfed5231 "" 43103
fetch https://ndownloader.figshare.com/files/51065297 "$D/Model.csv"                     675210d17675f3517b0ce39a3c274f16 "" 645696
fetch https://ndownloader.figshare.com/files/51065723 "$D/OmicsProfiles.csv"             7195088a5fc41eddb3f896c6e984a992 "" 254733
fetch https://ndownloader.figshare.com/files/51065339 "$D/OmicsDefaultModelProfiles.csv" 4d342a03701c0a4c0742fedb56c1de40 "" 90080
fetch https://ndownloader.figshare.com/files/51065489 "$D/OmicsExpressionProteinCodingGenesTPMLogp1.csv" 71794802b750ce77c422dad0720a40af "" 506628654
record_sha256 "$D"

# --- 24Q4 batch-corrected expression: SENSITIVITY option only, never a silent substitute ---
if $want_batch; then
  D=data/raw/depmap/24q4_sensitivity
  fetch https://ndownloader.figshare.com/files/51065492 "$D/OmicsExpressionProteinCodingGenesTPMLogp1BatchCorrected.csv" afefd19098154a62972eb975a55a36c9 "" 616166707
  record_sha256 "$D"
fi

# --- DepMap 23Q4 v1 Model.csv: identity drift audit only (not downloaded by default) ---
if $want_23q4; then
  D=data/raw/depmap/23q4_v1
  fetch https://ndownloader.figshare.com/files/43346895 "$D/Model.csv" c14f90f02609b9507c8b31e6d5db309b "" 582229
  record_sha256 "$D"
fi

# --- Yard et al. 2016 supplements (CC BY 4.0; no published checksums). PMC may refuse  ---
# --- scripted access; if so, download by browser and record retrieval_method: manual.   ---
if $want_yard; then
  D=data/raw/yard2016/ncomms11428_v1
  fetch https://pmc.ncbi.nlm.nih.gov/articles/instance/4848553/bin/ncomms11428-s2.xlsx "$D/ncomms11428-s2.xlsx" "" 504b0304 ""
  fetch https://pmc.ncbi.nlm.nih.gov/articles/instance/4848553/bin/ncomms11428-s1.pdf  "$D/ncomms11428-s1.pdf"  "" 25504446 ""
  record_sha256 "$D"
fi

# --- Optional context sources (no modelling role) ---
if $want_optional; then
  # The series matrix is regenerated by GEO (last modified 2026-08-04); it is not part of the
  # 2021-09-25 supplementary snapshot, so it is stored under its own dated folder.
  D=data/raw/geo_gse184119/suppl_20210925
  fetch https://ftp.ncbi.nlm.nih.gov/geo/series/GSE184nnn/GSE184119/suppl/filelist.txt "$D/filelist.txt" "" "" ""
  fetch https://ftp.ncbi.nlm.nih.gov/geo/series/GSE184nnn/GSE184119/suppl/GSE184119_RAW.tar "$D/GSE184119_RAW.tar" "" "" 3020800
  record_sha256 "$D"
  D=data/raw/geo_gse184119/matrix_$(date -u +%Y%m%d)
  fetch https://ftp.ncbi.nlm.nih.gov/geo/series/GSE184nnn/GSE184119/matrix/GSE184119_series_matrix.txt.gz "$D/GSE184119_series_matrix.txt.gz" "" 1f8b ""
  record_sha256 "$D"

  D=data/raw/iclac/v14
  fetch https://iclac.org/wp-content/uploads/Cross-Contaminations_v14_distribution.xlsx "$D/Cross-Contaminations_v14_distribution.xlsx" "" 504b0304 ""
  record_sha256 "$D"
fi

echo "Done. Next: PYTHONPATH=src python3 scripts/fetch_cellosaurus_phase_01.py"
