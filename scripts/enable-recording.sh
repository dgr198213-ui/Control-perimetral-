#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPLIANCE_DIR="$ROOT_DIR/compliance"
CONFIG="$ROOT_DIR/data/frigate-config/config.yml"

for evidence in carteleria-verificada encargo-tratamiento-firmado; do
  if [[ ! -f "$COMPLIANCE_DIR/$evidence" ]]; then
    echo "Bloqueado: falta compliance/$evidence" >&2
    exit 1
  fi
done

if grep -A1 -Eq '^record:$' "$CONFIG" | grep -Eq '^  enabled: true$'; then
  echo "La grabación ya está habilitada; no se realizan cambios."
  exit 0
fi

cp "$CONFIG" "$CONFIG.before-activation.$(date +%Y%m%d%H%M%S).bak"
python3 - "$CONFIG" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
record_needle = "record:\n  enabled: false"
snapshot_needle = "snapshots:\n  enabled: false"
if record_needle not in text or snapshot_needle not in text:
    raise SystemExit("No se encontró el bloqueo esperado; revisión manual necesaria")
text = text.replace(record_needle, "record:\n  enabled: true", 1)
text = text.replace(snapshot_needle, "snapshots:\n  enabled: true", 1)
path.write_text(text)
PY

echo "Grabación habilitada tras verificar las dos evidencias. Reinicia con: docker compose up -d --force-recreate frigate notifier"
