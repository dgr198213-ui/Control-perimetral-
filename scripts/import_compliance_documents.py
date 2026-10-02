#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

source = Path('/home/ubuntu/upload/pasted_content.txt')
target = Path('compliance')
text = source.read_text(encoding='utf-8')
decoder = json.JSONDecoder()
for identifier in ('carteleria-verificada', 'encargo-tratamiento-firmado'):
    heading = f'compliance/{identifier}.json'
    start = text.index(heading) + len(heading)
    object_start = text.index('{', start)
    data, _ = decoder.raw_decode(text[object_start:])
    if data.get('id') != identifier or data.get('verification', {}).get('verified') is not True:
        raise SystemExit(f'Documento no verificado o identificador incorrecto: {identifier}')
    output = target / f'{identifier}.json'
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    marker = target / identifier
    marker.write_text(f'Verificado según {output.name}; estado={data["status"]}; revisión={data["verification"]["verified_at"]}\n', encoding='utf-8')
    print(f'Importado: {output}')
