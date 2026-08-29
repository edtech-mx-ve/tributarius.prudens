# Sprint 19I.18P — gate integral local de preproducción

## Objetivo

Consolidar en un único gate fail-closed la cadena 19L → 19M → 19N → 19O.

Este sprint distingue explícitamente:

- **suficiencia técnica local**, que puede quedar aceptada;
- **autorización de publicación**, que permanece bloqueada.

No cambia ni relaja los gates jurídicos o temporales.

## Criterios de aceptación

La cadena técnica debe acreditar:

- procedencia y política temporal fail-closed de 19L;
- integridad/reproducibilidad del candidato 19M;
- cold-start aislado de 19N;
- descarga sin credenciales, recarga offline y consulta semántica de 19O.

El resultado esperado es:

- `technical_chain_complete=True`
- `embedding_dependency_complete=True`
- `decision=DO_NOT_PUBLISH`
- `public_release_allowed=False`
- `git_push_allowed=False`
- `render_deploy_allowed=False`

## Implementación

```powershell
Expand-Archive `
  -Path "$env:USERPROFILE\Downloads\tributarius-prudens-sprint19I.18P-patch.zip" `
  -DestinationPath "." `
  -Force

pytest tests/test_public_release_preproduction_gate_19i18p.py -v

ruff check .
mypy app scripts
pytest

python -m scripts.validate_public_release_preproduction_gate_19i18p
```

19P es un gate mayor de cierre local, por lo que aquí sí corresponde una sola
ejecución integral de Ruff, mypy y pytest.

## Limitaciones

La aceptación técnica no autoriza redistribución ni despliegue. Permanecen como
bloqueos explícitos la revisión humana de redistribución, la vigencia temporal
incompleta y la revisión de licencia del modelo de embeddings.
