#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_ROOT"
python3 -m venv .venv
.venv/bin/python -m pip install -e .
if [ ! -f web/dist/index.html ]; then
  command -v npm >/dev/null || { echo 'No built web assets. Deploy the prepared package or install Node.js 20+ and npm.'; exit 2; }
  npm ci
  .venv/bin/python scripts/generate-demo.py --georeference-example
  npm run build
fi
if [ ! -f config/site.local.json ]; then cp config/site.example.json config/site.local.json; fi
echo 'RPi dependencies ready. Edit config/site.local.json with measured coordinates/calibration.'
echo 'Run .venv/bin/python -m ble_inventory.cli serve --mode ble --host 0.0.0.0 --config config/site.local.json'
