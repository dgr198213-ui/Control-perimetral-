#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DB="${CONTROL_API_DB:-${ROOT_DIR}/data/control-api.sqlite3}"
BACKUP_ROOT="${BACKUP_DIR:-${ROOT_DIR}/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_ROOT}/control-perimetral-${STAMP}"

mkdir -p "${DEST}/data" "${DEST}/config" "${DEST}/compliance"
python3 "${ROOT_DIR}/scripts/sqlite_backup.py" "${SOURCE_DB}" "${DEST}/data/control-api.sqlite3"

if [[ -d "${ROOT_DIR}/data/frigate-config" ]]; then
  cp -a "${ROOT_DIR}/data/frigate-config/." "${DEST}/config/"
fi
if [[ -d "${ROOT_DIR}/compliance" ]]; then
  cp -a "${ROOT_DIR}/compliance/." "${DEST}/compliance/"
fi

cat > "${DEST}/manifest.txt" <<EOF
created_at=${STAMP}
source_db=${SOURCE_DB}
repository=$(basename "${ROOT_DIR}")
EOF

printf 'Backup creado: %s\n' "${DEST}"
