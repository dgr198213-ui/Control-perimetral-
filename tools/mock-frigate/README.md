# Mock Frigate

Servidor mínimo local para comprobar healthchecks y pruebas de integración de `control-api` sin conectar cámaras reales. Solo expone `GET /api/version` en `127.0.0.1:5000`.

```bash
python3 tools/mock-frigate/mock.py
curl http://127.0.0.1:5000/api/version
```

No contiene credenciales, streams ni datos de una finca real.
