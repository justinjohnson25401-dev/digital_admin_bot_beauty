#!/usr/bin/env bash
set -euo pipefail

# Digital Admin — backup script
# Creates a tar.gz with config + db files.

INSTALL_DIR="/opt/digital-admin"
BACKUP_DIR="/opt/digital-admin-backups"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

TS="$(date +%F_%H%M%S)"
ARCHIVE="$BACKUP_DIR/digital-admin-backup.$TS.tar.gz"

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "Install dir not found: $INSTALL_DIR"
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Copy important files (ignore if missing)
mkdir -p "$TMP_DIR/configs"
if [[ -f "$INSTALL_DIR/configs/client_lite.json" ]]; then
  cp "$INSTALL_DIR/configs/client_lite.json" "$TMP_DIR/configs/"
fi

if [[ -f "$INSTALL_DIR/.env" ]]; then
  cp "$INSTALL_DIR/.env" "$TMP_DIR/"
fi

cp "$INSTALL_DIR"/db_*.sqlite "$TMP_DIR/" 2>/dev/null || true

# Package
( cd "$TMP_DIR" && tar -czf "$ARCHIVE" . )

echo "Backup created: $ARCHIVE"

# Retention
if [[ "$KEEP_DAYS" =~ ^[0-9]+$ ]]; then
  find "$BACKUP_DIR" -type f -name 'digital-admin-backup.*.tar.gz' -mtime "+$KEEP_DAYS" -delete || true
fi
