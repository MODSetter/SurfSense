#!/usr/bin/env bash
set -euo pipefail

pdf=${1:?usage: render_pages.sh PDF [OUTPUT_DIR]}
output_dir=${2:-/tmp/pdf-pages}

test -s "$pdf"
mkdir -p "$output_dir"
rm -f "$output_dir"/page-*.jpg
pdftoppm -jpeg -r 100 "$pdf" "$output_dir/page"

shopt -s nullglob
pages=("$output_dir"/page-*.jpg)
((${#pages[@]} > 0))
printf '%s\n' "${pages[@]}"
