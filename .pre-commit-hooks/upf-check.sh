#!/usr/bin/env bash
# upf-insight pre-commit hook: validate staged .upf/.tcl files.
# SDC_TOOLS-style contract: UPF_INSIGHT_MODE=block (default) fails the commit
# on error findings; UPF_INSIGHT_MODE=warn only reports.
set -u

MODE="${UPF_INSIGHT_MODE:-block}"

if ! command -v upf-insight >/dev/null 2>&1; then
  echo "upf-check: upf-insight is not installed; skipping (pip install upf-insight)" >&2
  exit 0
fi

status=0
for f in "$@"; do
  [ -f "$f" ] || continue
  echo "upf-check: $f"
  if ! out="$(upf-insight check "$f" 2>&1)"; then
    printf '%s\n' "$out"
    if [ "$MODE" = "block" ]; then
      status=1
    fi
  fi
done

if [ "$status" -ne 0 ]; then
  echo "upf-check: staged UPF files have errors (commit blocked)." >&2
  echo "upf-check: fix the findings or commit with UPF_INSIGHT_MODE=warn." >&2
fi
exit "$status"
