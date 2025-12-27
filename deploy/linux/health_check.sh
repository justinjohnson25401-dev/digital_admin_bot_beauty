#!/usr/bin/env bash
set -euo pipefail

# Digital Admin — Health Check Script
# Проверяет состояние сервисов и БД, возвращает exit code для мониторинга

INSTALL_DIR="/opt/digital-admin"
CLIENT_SERVICE="digital-admin-client"
ADMIN_SERVICE="digital-admin-admin"
EXIT_CODE=0

check_service() {
    local service=$1
    if systemctl is-active --quiet "$service"; then
        echo "✅ $service: running"
    else
        echo "❌ $service: NOT running"
        EXIT_CODE=1
    fi
}

check_db() {
    local db_path=$(ls -1 "$INSTALL_DIR"/db_*.sqlite 2>/dev/null | head -n 1)
    if [[ -z "$db_path" ]]; then
        echo "❌ Database: NOT FOUND"
        EXIT_CODE=1
        return
    fi
    
    # Проверяем доступность БД через SQLite
    if command -v sqlite3 >/dev/null 2>&1; then
        if sqlite3 "$db_path" "SELECT 1" >/dev/null 2>&1; then
            echo "✅ Database: accessible"
        else
            echo "❌ Database: NOT accessible (locked or corrupted)"
            EXIT_CODE=1
        fi
    else
        echo "⚠️  Database: exists (sqlite3 not installed for deep check)"
    fi
}

check_disk_space() {
    local usage=$(df -h "$INSTALL_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $usage -gt 90 ]]; then
        echo "❌ Disk space: ${usage}% (CRITICAL)"
        EXIT_CODE=1
    elif [[ $usage -gt 80 ]]; then
        echo "⚠️  Disk space: ${usage}% (WARNING)"
    else
        echo "✅ Disk space: ${usage}%"
    fi
}

check_logs() {
    local client_errors=$(journalctl -u "$CLIENT_SERVICE" -n 100 --no-pager 2>/dev/null | grep -i "error\|critical\|exception" | wc -l)
    local admin_errors=$(journalctl -u "$ADMIN_SERVICE" -n 100 --no-pager 2>/dev/null | grep -i "error\|critical\|exception" | wc -l)
    
    if [[ $client_errors -gt 10 ]]; then
        echo "⚠️  Client bot: $client_errors errors in last 100 lines"
        EXIT_CODE=1
    else
        echo "✅ Client bot: $client_errors errors"
    fi
    
    if [[ $admin_errors -gt 10 ]]; then
        echo "⚠️  Admin bot: $admin_errors errors in last 100 lines"
        EXIT_CODE=1
    else
        echo "✅ Admin bot: $admin_errors errors"
    fi
}

echo "=== Digital Admin Health Check ==="
echo "Time: $(date)"
echo

check_service "$CLIENT_SERVICE"
check_service "$ADMIN_SERVICE"
check_db
check_disk_space
check_logs

echo
if [[ $EXIT_CODE -eq 0 ]]; then
    echo "✅ All checks passed"
else
    echo "❌ Some checks failed"
fi

exit $EXIT_CODE
