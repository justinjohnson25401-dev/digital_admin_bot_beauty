#!/usr/bin/env bash
set -euo pipefail

# Digital Admin — quick health-check for Ubuntu systemd installation

INSTALL_DIR="/opt/digital-admin"
CLIENT_SERVICE="digital-admin-client"
ADMIN_SERVICE="digital-admin-admin"

print_section() {
  echo
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

print_section "Digital Admin — STATUS"

echo "Time: $(date)"
echo "Host: $(hostname)"

echo
if [[ -d "$INSTALL_DIR" ]]; then
  echo "Install dir: $INSTALL_DIR (OK)"
else
  echo "Install dir: $INSTALL_DIR (NOT FOUND)"
fi

print_section "Files"
if [[ -f "$INSTALL_DIR/.env" ]]; then
  echo ".env: OK"
else
  echo ".env: NOT FOUND"
fi

if [[ -f "$INSTALL_DIR/configs/client_lite.json" ]]; then
  echo "configs/client_lite.json: OK"
else
  echo "configs/client_lite.json: NOT FOUND"
fi

DB_COUNT=$(ls -1 "$INSTALL_DIR"/db_*.sqlite 2>/dev/null | wc -l | tr -d ' ')
echo "db_*.sqlite count: $DB_COUNT"

print_section "systemd services"
if command -v systemctl >/dev/null 2>&1; then
  systemctl --no-pager --full status "$CLIENT_SERVICE" || true
  echo
  systemctl --no-pager --full status "$ADMIN_SERVICE" || true
else
  echo "systemctl not found"
fi

print_section "Last logs (client)"
if command -v journalctl >/dev/null 2>&1; then
  journalctl -u "$CLIENT_SERVICE" -n 80 --no-pager || true
else
  echo "journalctl not found"
fi

print_section "Last logs (admin)"
if command -v journalctl >/dev/null 2>&1; then
  journalctl -u "$ADMIN_SERVICE" -n 80 --no-pager || true
else
  echo "journalctl not found"
fi

print_section "Hints"
cat <<'EOF'
- If BOT_TOKEN / ADMIN_BOT_TOKEN is wrong: edit /opt/digital-admin/.env and restart services.
  sudo systemctl restart digital-admin-client
  sudo systemctl restart digital-admin-admin

- If config is broken JSON: check /opt/digital-admin/configs/client_lite.json

- If you forgot admin PIN:
  sudo bash deploy/linux/reset_pin.sh

- If you need to rollback from backup:
  sudo bash deploy/linux/restore.sh

- If you need to check DB schema version:
  sudo bash deploy/linux/db_info.sh

- Quick post-update check:
  sudo bash deploy/linux/smoke_test.sh

- If services are missing:
  sudo bash deploy/linux/install.sh
EOF
