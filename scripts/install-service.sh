#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_USER="$(id -un)"
if [ ! -x "$TASK_ROOT/.venv/bin/python" ]; then echo 'Run setup-rpi.sh first.'; exit 2; fi
TASK_CONFIG="config/site.local.json"
if [ -f "$TASK_ROOT/config/private/site.cloud.json" ]; then TASK_CONFIG="config/private/site.cloud.json"; fi
test -f "$TASK_ROOT/$TASK_CONFIG" || { echo 'Missing site config'; exit 2; }
# Quote filesystem paths for systemd; reject control characters and expansion syntax.
case "$TASK_ROOT" in *$'\n'*|*'"'*|*'%'*|*'\\'*) echo 'Unsupported service install path'; exit 2;; esac
sudo tee /etc/systemd/system/ble-inventory.service >/dev/null <<EOF
[Unit]
Description=BLE mobile inventory
After=network-online.target bluetooth.service
Wants=network-online.target

[Service]
Type=simple
User=$TASK_USER
WorkingDirectory=$TASK_ROOT
ExecStart="$TASK_ROOT/.venv/bin/python" -m ble_inventory.cli serve --mode ble --host 0.0.0.0 --config $TASK_CONFIG
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=5
UMask=0077

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now ble-inventory.service
systemctl --no-pager status ble-inventory.service
