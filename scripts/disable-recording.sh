#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT_DIR/frigate/config.yml"
python3 - "$CONFIG" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
text = text.replace("record:\n  enabled: true", "record:\n  enabled: false", 1)
text = text.replace("snapshots:\n  enabled: true", "snapshots:\n  enabled: false", 1)
path.write_text(text)
PY

echo "Grabación y snapshots desactivados. Reinicia con: docker compose up -d --force-recreate frigate notifier"
