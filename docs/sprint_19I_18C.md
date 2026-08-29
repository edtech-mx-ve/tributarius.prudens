# Sprint 19I.18C — wiring local del bootstrap de despliegue

Este incremento conecta el instalador 19I.18B al blueprint de Render, sin
desplegar todavía.

## Decisiones

- `render.yaml` ejecuta el bootstrap después de instalar el paquete;
- `RUNTIME_RELEASE_SHA256` queda fijado al bundle local aprobado:
  `687c9f6bba0b166b3728ce387d560644523d260cde1f7a298655954e490cbda4`;
- `RUNTIME_RELEASE_URL` queda como variable externa `sync: false`;
- el build falla si la URL no existe, no usa HTTPS o el hash no coincide;
- producción exige el runtime semántico v2 y el registro temporal;
- `REQUIRE_RAG_ARTIFACTS=true`;
- `REQUIRE_TEMPORAL_PROVENANCE_REGISTRY=true`.

No existe todavía una URL pública fijada y por eso este sprint sigue siendo
exclusivamente local.

## Implementación local

```powershell
pytest tests/test_runtime_release_bootstrap_19i18c.py -v
pytest tests/test_deployment_runtime_bootstrap_19i18c.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.validate_deployment
python -m scripts.audit_sprint19_local_acceptance_19i17
python -m scripts.smoke_temporal_runtime_e2e_19i16
```

No ejecutar `git push` ni desplegar en Render.
