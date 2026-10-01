#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR_INPUT="${1:-}"
TARGET_DB="${CONTROL_API_DB:-${ROOT_DIR}/data/control-api.sqlite3}"

if [[ -z "${BACKUP_DIR_INPUT}" || ! -d "${BACKUP_DIR_INPUT}" ]]; then
  printf 'Uso: %s BACKUP_DIR\n' "$0" >&2
  exit 2
fi
if [[ ! -f "${BACKUP_DIR_INPUT}/data/control-api.sqlite3" ]]; then
  printf 'Backup inválido: falta data/control-api.sqlite3\n' >&2
  exit 1
fi
if [[ "${RESTORE_CONFIRM:-}" != "YES" ]]; then
  printf 'La restauración reemplazará %s. Establece RESTORE_CONFIRM=YES para continuar.\n' "${TARGET_DB}" >&2
  exit 2
fi

mkdir -p "$(dirname "${TARGET_DB}")"
TEMP_DB="${TARGET_DB}.restore.tmp"
rm -f "${TEMP_DB}"
python3 "${ROOT_DIR}/scripts/sqlite_backup.py" "${BACKUP_DIR_INPUT}/data/control-api.sqlite3" "${TEMP_DB}"
mv "${TEMP_DB}" "${TARGET_DB}"

if [[ -d "${BACKUP_DIR_INPUT}/config" ]]; then
  mkdir -p "${ROOT_DIR}/data/frigate-config"
  cp -a "${BACKUP_DIR_INPUT}/config/." "${ROOT_DIR}/data/frigate-config/"
fi
if [[ -d "${BACKUP_DIR_INPUT}/compliance" ]]; then
  mkdir -p "${ROOT_DIR}/compliance"
  cp -a "${BACKUP_DIR_INPUT}/compliance/." "${ROOT_DIR}/compliance/"
fi

printf 'Restauración completada: %s\n' "${TARGET_DB}"
