#!/usr/bin/env bash
set -euo pipefail

# Digital Admin — DB diagnostics
# Shows schema version, tables, and key columns.

INSTALL_DIR="/opt/digital-admin"
DB_GLOB="$INSTALL_DIR/db_*.sqlite"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo bash deploy/linux/db_info.sh"
  exit 1
fi

DB_PATH="${1:-}"
if [[ -z "$DB_PATH" ]]; then
  DB_PATH=$(ls -1 $DB_GLOB 2>/dev/null | head -n 1 || true)
fi

if [[ -z "$DB_PATH" || ! -f "$DB_PATH" ]]; then
  echo "DB file not found. Pass explicit path, e.g.:"
  echo "  sudo bash deploy/linux/db_info.sh /opt/digital-admin/db_xxx.sqlite"
  exit 1
fi

echo "DB: $DB_PATH"

python3 - <<PY
import sqlite3

path = r"$DB_PATH"
con = sqlite3.connect(path)
cur = con.cursor()

def table_exists(name: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,))
    return cur.fetchone() is not None

def columns(name: str):
    try:
        cur.execute(f"PRAGMA table_info({name})")
        return [r[1] for r in cur.fetchall()]
    except Exception:
        return []

version = 0
if table_exists('schema_migrations'):
    cur.execute('SELECT version FROM schema_migrations LIMIT 1')
    row = cur.fetchone()
    if row and row[0] is not None:
        try:
            version = int(row[0])
        except Exception:
            version = 0

print(f"schema_version: {version}")

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print("tables:")
for (name,) in cur.fetchall():
    print(f"- {name}")

for t in ['orders', 'users']:
    if table_exists(t):
        cols = columns(t)
        print(f"\n{t} columns ({len(cols)}):")
        for c in cols:
            print(f"- {c}")
    else:
        print(f"\n{t}: MISSING")

con.close()
PY
