#!/usr/bin/env bash
set -euo pipefail

# Digital Admin — updater for Ubuntu systemd installation
# Assumes installation directory: /opt/digital-admin
# Updates code from the current folder into /opt/digital-admin and restarts services.

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo bash deploy/linux/update.sh"
  exit 1
fi

PROJECT_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALL_DIR="/opt/digital-admin"
RUN_USER="digitaladmin"
RUN_GROUP="$RUN_USER"

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "Install dir not found: $INSTALL_DIR"
  echo "Run installer first: sudo bash deploy/linux/install.sh"
  exit 1
fi

echo "==> Stopping services"
systemctl stop digital-admin-client.service || true
systemctl stop digital-admin-admin.service || true

BACKUP_DIR="/opt/digital-admin-backups"
mkdir -p "$BACKUP_DIR"
TS="$(date +%F_%H%M%S)"

echo "==> Backing up config and database"
if [[ -f "$INSTALL_DIR/configs/client_lite.json" ]]; then
  cp "$INSTALL_DIR/configs/client_lite.json" "$BACKUP_DIR/client_lite.json.$TS"
fi
cp "$INSTALL_DIR"/db_*.sqlite "$BACKUP_DIR/" 2>/dev/null || true

echo "==> Syncing project to $INSTALL_DIR (preserving .env, configs, db)"
rsync -a --delete \
  --exclude ".env" \
  --exclude "configs/" \
  --exclude "db_*.sqlite" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".venv/" \
  --exclude ".git/" \
  "$PROJECT_SRC_DIR/" "$INSTALL_DIR/"

chown -R "$RUN_USER:$RUN_GROUP" "$INSTALL_DIR"

chmod +x "$INSTALL_DIR/deploy/linux/"*.sh 2>/dev/null || true

if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
  echo "==> venv not found, creating"
  sudo -u "$RUN_USER" bash -lc "python3 -m venv '$INSTALL_DIR/.venv'"
fi

echo "==> Installing/updating Python deps"
sudo -u "$RUN_USER" bash -lc "'$INSTALL_DIR/.venv/bin/python' -m pip install --upgrade pip"
sudo -u "$RUN_USER" bash -lc "'$INSTALL_DIR/.venv/bin/python' -m pip install -r '$INSTALL_DIR/requirements.txt'"

echo "==> Reloading systemd"
systemctl daemon-reload

echo "==> Ensuring backup timer enabled"
systemctl enable --now digital-admin-backup.timer || true

echo "==> Starting services"
systemctl restart digital-admin-client.service
systemctl restart digital-admin-admin.service

echo "==> Done"
echo "Logs (client): journalctl -u digital-admin-client -f"
echo "Logs (admin):  journalctl -u digital-admin-admin  -f"
