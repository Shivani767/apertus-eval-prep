#!/usr/bin/env bash
# Offline smoke test: full test suite plus one deterministic mock evaluation.
#
# The interpreter is resolved explicitly rather than calling a bare `python`.
# A bare `python` is not reliably on PATH unless a virtualenv is *activated*,
# which made this script fail outright for anyone invoking it as
# `bash scripts/smoke.sh`. Resolution order:
#   1. $PYTHON, if the caller set one
#   2. the repository's own .venv
#   3. python3
#   4. python
# and it exits with an actionable message if none of them exist, rather than
# failing later with "command not found" and a useless exit code.
set -euo pipefail

cd "$(dirname "$0")/.."

resolve_python() {
  if [ -n "${PYTHON:-}" ]; then
    printf '%s' "$PYTHON"
    return
  fi
  for candidate in .venv/bin/python python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return
    fi
  done
}

PY="$(resolve_python)"
if [ -z "$PY" ]; then
  echo "smoke.sh: no Python interpreter found." >&2
  echo "  Create a virtualenv (.venv) or set PYTHON=/path/to/python and retry." >&2
  exit 127
fi
export PYTHON="$PY"

echo "Using interpreter: $PY"
"$PY" -m pytest -q
"$PY" -m apertus_eval_prep eval --config configs/smoke.yaml --out results/smoke.json
echo "Smoke JSON written to results/smoke.json"
