#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
db_path = Path(__import__('os').environ.get('CONTROL_API_DB', root / 'data/control-api.sqlite3'))
now = datetime.now(timezone.utc).isoformat()
connection = sqlite3.connect(db_path)
try:
    row = connection.execute('SELECT kill_switch FROM compliance WHERE id = 1').fetchone()
    if row is None:
        raise SystemExit('No existe la fila de cumplimiento; la base no está inicializada')
    if row[0]:
        raise SystemExit('El kill-switch está activo; libéralo mediante el flujo autenticado antes de activar')
    connection.execute(
        'UPDATE compliance SET signage_confirmed=1, mandate_confirmed=1, kill_switch=0, updated_at=? WHERE id=1',
        (now,),
    )
    connection.execute(
        'INSERT INTO audit_log(action, entity, entity_id, details, created_at) VALUES (?, ?, ?, ?, ?)',
        ('confirm', 'compliance', '1', json.dumps({
            'actor': 'property_owner',
            'source': 'verified_documents',
            'signage': 'carteleria-verificada.json',
            'processing_agreement': 'not_applicable',
            'reason': 'Documentos verificados aportados por el propietario',
        }, ensure_ascii=False, sort_keys=True), now),
    )
    connection.commit()
    print('COMPLIANCE_ACTIVATED')
finally:
    connection.close()
