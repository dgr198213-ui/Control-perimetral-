#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPLIANCE_DIR="$ROOT_DIR/compliance"
CONFIG="$ROOT_DIR/frigate/config.yml"

for evidence in carteleria-verificada encargo-tratamiento-firmado; do
  if [[ ! -f "$COMPLIANCE_DIR/$evidence" ]]; then
    echo "Bloqueado: falta compliance/$evidence" >&2
    exit 1
  fi
done

if grep -Eq '^  enabled: true' "$CONFIG"; then
  echo "La grabación ya está habilitada; no se realizan cambios."
  exit 0
fi

cp "$CONFIG" "$CONFIG.before-activation.$(date +%Y%m%d%H%M%S).bak"
python3 - "$CONFIG" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
needle = "record:\n  enabled: false"
if needle not in text:
    raise SystemExit("No se encontró el bloqueo esperado; revisión manual necesaria")
path.write_text(text.replace(needle, "record:\n  enabled: true", 1))
PY

echo "Grabación habilitada tras verificar las dos evidencias. Reinicia con: docker compose up -d --force-recreate frigate notifier"
