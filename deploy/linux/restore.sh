#!/usr/bin/env bash
set -euo pipefail

# Digital Admin — restore from backup archive
# Usage:
#   sudo bash deploy/linux/restore.sh /opt/digital-admin-backups/digital-admin-backup.YYYY-MM-DD_HHMMSS.tar.gz
#   sudo bash deploy/linux/restore.sh   (interactive list)

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo bash deploy/linux/restore.sh"
  exit 1
fi

INSTALL_DIR="/opt/digital-admin"
BACKUP_DIR="/opt/digital-admin-backups"

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "Install dir not found: $INSTALL_DIR"
  exit 1
fi

pick_archive() {
  echo "Available backups in $BACKUP_DIR:"
  ls -1t "$BACKUP_DIR"/digital-admin-backup.*.tar.gz 2>/dev/null || true
  echo
  read -r -p "Enter full path to archive: " path
  echo "$path"
}

ARCHIVE="${1:-}"
if [[ -z "$ARCHIVE" ]]; then
  ARCHIVE="$(pick_archive)"
fi

if [[ ! -f "$ARCHIVE" ]]; then
  echo "Archive not found: $ARCHIVE"
  exit 1
fi

TS="$(date +%F_%H%M%S)"
PRE_DIR="$BACKUP_DIR/pre_restore.$TS"
mkdir -p "$PRE_DIR"

echo "==> Saving current state to $PRE_DIR"
cp -f "$INSTALL_DIR/configs/client_lite.json" "$PRE_DIR/" 2>/dev/null || true
cp -f "$INSTALL_DIR"/db_*.sqlite "$PRE_DIR/" 2>/dev/null || true

echo "==> Stopping services"
systemctl stop digital-admin-client.service || true
systemctl stop digital-admin-admin.service || true

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "==> Extracting $ARCHIVE"
tar -xzf "$ARCHIVE" -C "$TMP_DIR"

# Restore config
if [[ -f "$TMP_DIR/configs/client_lite.json" ]]; then
  mkdir -p "$INSTALL_DIR/configs"
  cp -f "$TMP_DIR/configs/client_lite.json" "$INSTALL_DIR/configs/client_lite.json"
else
  echo "WARN: configs/client_lite.json not found in archive"
fi

# Restore db files (if any)
shopt -s nullglob
DB_FILES=("$TMP_DIR"/db_*.sqlite)
if (( ${#DB_FILES[@]} > 0 )); then
  cp -f "$TMP_DIR"/db_*.sqlite "$INSTALL_DIR/"
else
  echo "WARN: db_*.sqlite not found in archive"
fi
shopt -u nullglob

echo "==> Fixing ownership"
chown -R digitaladmin:digitaladmin "$INSTALL_DIR" || true

echo "==> Starting services"
systemctl start digital-admin-client.service || true
systemctl start digital-admin-admin.service || true

echo "==> Done"
echo "Previous state saved in: $PRE_DIR"
