#!/usr/bin/env bash
set -euo pipefail

# BOT-BUSINESS V2.0 — Ubuntu one-command installer (systemd)
# Installs 2 services:
# - digital-admin-client
# - digital-admin-admin

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo bash deploy/linux/install.sh"
  exit 1
fi

PROJECT_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALL_DIR="/opt/digital-admin"
RUN_USER="digitaladmin"
RUN_GROUP="$RUN_USER"

echo "==> Installing OS dependencies"
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip \
  ca-certificates \
  rsync \
  tzdata

if ! id -u "$RUN_USER" >/dev/null 2>&1; then
  echo "==> Creating system user: $RUN_USER"
  useradd --system --create-home --home-dir "/home/${RUN_USER}" --shell /usr/sbin/nologin "$RUN_USER"
fi

mkdir -p "$INSTALL_DIR"

echo "==> Syncing project to $INSTALL_DIR"
rsync -a --delete \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".venv/" \
  --exclude ".git/" \
  "$PROJECT_SRC_DIR/" "$INSTALL_DIR/"

chown -R "$RUN_USER:$RUN_GROUP" "$INSTALL_DIR"

chmod +x "$INSTALL_DIR/deploy/linux/"*.sh 2>/dev/null || true

echo "==> Creating venv"
sudo -u "$RUN_USER" bash -lc "python3 -m venv '$INSTALL_DIR/.venv'"

echo "==> Installing Python deps"
sudo -u "$RUN_USER" bash -lc "'$INSTALL_DIR/.venv/bin/python' -m pip install --upgrade pip"
sudo -u "$RUN_USER" bash -lc "'$INSTALL_DIR/.venv/bin/python' -m pip install -r '$INSTALL_DIR/requirements.txt'"

if [[ ! -f "$INSTALL_DIR/.env" || ! -f "$INSTALL_DIR/configs/client_lite.json" ]]; then
  echo "==> First-time setup"
  echo "Running interactive installer: python setup.py"
  echo "Follow prompts to enter BOTH tokens (client + admin)"
  sudo -u "$RUN_USER" bash -lc "cd '$INSTALL_DIR' && '$INSTALL_DIR/.venv/bin/python' setup.py"
else
  echo "==> Detected existing .env and configs/client_lite.json — skipping setup"
fi

CLIENT_UNIT_PATH="/etc/systemd/system/digital-admin-client.service"
ADMIN_UNIT_PATH="/etc/systemd/system/digital-admin-admin.service"
BACKUP_SERVICE_PATH="/etc/systemd/system/digital-admin-backup.service"
BACKUP_TIMER_PATH="/etc/systemd/system/digital-admin-backup.timer"

echo "==> Writing systemd units"
cat > "$CLIENT_UNIT_PATH" <<EOF
[Unit]
Description=Digital Admin - Client Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/.venv/bin/python ${INSTALL_DIR}/main.py --config ${INSTALL_DIR}/configs/client_lite.json
Restart=always
RestartSec=3

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${INSTALL_DIR}

[Install]
WantedBy=multi-user.target
EOF

cat > "$ADMIN_UNIT_PATH" <<EOF
[Unit]
Description=Digital Admin - Admin Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/.venv/bin/python ${INSTALL_DIR}/admin_bot/main.py --config ${INSTALL_DIR}/configs/client_lite.json
Restart=always
RestartSec=3

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${INSTALL_DIR}

[Install]
WantedBy=multi-user.target
EOF

cat > "$BACKUP_SERVICE_PATH" <<EOF
[Unit]
Description=Digital Admin - Backup

[Service]
Type=oneshot
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/deploy/linux/backup.sh
EOF

cat > "$BACKUP_TIMER_PATH" <<EOF
[Unit]
Description=Digital Admin - Daily Backup Timer

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "==> Enabling & starting services"
systemctl daemon-reload
systemctl enable --now digital-admin-client.service
systemctl enable --now digital-admin-admin.service
systemctl enable --now digital-admin-backup.timer

echo "==> Done"
echo "Client service:  systemctl status digital-admin-client --no-pager"
echo "Admin service:   systemctl status digital-admin-admin  --no-pager"
echo "Logs (client):   journalctl -u digital-admin-client -f"
echo "Logs (admin):    journalctl -u digital-admin-admin  -f"
echo "Backups:         systemctl list-timers digital-admin-backup.timer --no-pager"
