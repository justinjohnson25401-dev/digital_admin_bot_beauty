#!/usr/bin/env bash
set -euo pipefail

# Digital Admin — reset admin PIN (removes admin_pin_hash from config)

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo bash deploy/linux/reset_pin.sh"
  exit 1
fi

INSTALL_DIR="/opt/digital-admin"
CONFIG_PATH="$INSTALL_DIR/configs/client_lite.json"
BACKUP_DIR="/opt/digital-admin-backups"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config not found: $CONFIG_PATH"
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TS="$(date +%F_%H%M%S)"
cp "$CONFIG_PATH" "$BACKUP_DIR/client_lite.json.before_pin_reset.$TS"

echo "==> Removing admin_pin_hash from $CONFIG_PATH"
python3 - <<PY
import json
from pathlib import Path

path = Path(r"$CONFIG_PATH")
raw = path.read_text(encoding="utf-8")
config = json.loads(raw)

if 'admin_pin_hash' in config:
    del config['admin_pin_hash']

path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK")
PY

echo "==> Restarting admin service"
systemctl restart digital-admin-admin.service || true

echo "==> Done"
echo "Backup saved: $BACKUP_DIR/client_lite.json.before_pin_reset.$TS"
