#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest -q
python -m apertus_eval_prep eval --config configs/smoke.yaml --out results/smoke.json
echo "Smoke JSON written to results/smoke.json"
