#!/usr/bin/env bash
set -euo pipefail

# Digital Admin — quick smoke test after install/update

INSTALL_DIR="/opt/digital-admin"
CLIENT_SERVICE="digital-admin-client"
ADMIN_SERVICE="digital-admin-admin"

print_section() {
  echo
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

print_section "Smoke test"
echo "Time: $(date)"

echo
if [[ -d "$INSTALL_DIR" ]]; then
  echo "Install dir: $INSTALL_DIR (OK)"
else
  echo "Install dir: $INSTALL_DIR (NOT FOUND)"
fi

print_section "systemd status"
systemctl --no-pager --full status "$CLIENT_SERVICE" || true
echo
systemctl --no-pager --full status "$ADMIN_SERVICE" || true

echo
systemctl list-timers digital-admin-backup.timer --no-pager || true

print_section "DB info"
sudo bash deploy/linux/db_info.sh || true

print_section "Last logs (client)"
journalctl -u "$CLIENT_SERVICE" -n 120 --no-pager || true

print_section "Last logs (admin)"
journalctl -u "$ADMIN_SERVICE" -n 120 --no-pager || true

print_section "Done"
echo "If services are failed:"
echo "- Run: sudo bash deploy/linux/status.sh"
echo "- Restore: sudo bash deploy/linux/restore.sh"
