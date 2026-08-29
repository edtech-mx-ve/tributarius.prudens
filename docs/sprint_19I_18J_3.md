# Sprint 19I.18J.3 — matriz integral de decisión de publicación

## Objetivo

Consolidar en una sola salida los gates ya construidos:

- 19I.18E: política de redistribución;
- 19I.18F: evidencia jurídica por documento;
- 19I.18G: conformidad técnica del contenido normativo;
- 19I.18I: runtime -> PDF local;
- 19I.18J/J.1: PDF local -> fuente oficial.

La matriz **no promueve** documentos. Su objetivo es hacer explícito el bloqueo
exacto por fuente para decidir el siguiente incremento sin mezclar problemas
de red, procedencia, conformidad y licencia.

## Implementación

```powershell
pytest tests/test_runtime_publication_decision_matrix_19i18j3.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest

python -m scripts.build_runtime_publication_decision_matrix_19i18j3
```

Resultado:

`reports/sprint19I18J3/runtime_publication_decision_matrix.json`

## Criterios

- `rmf_2026` puede tener procedencia oficial exacta y aun así quedar bloqueada
  por `redistribution_policy_not_verified`;
- los 13 documentos de Cámara con timeout se clasifican como evidencia externa
  pendiente, no como hash distinto;
- UNAM y PRODECON permanecen en revisión separada;
- `public_release_allowed` solo puede ser True si todos los documentos están
  individualmente listos, lo cual no debe ocurrir con el estado actual.


## Hotfix r1

Corrige el contrato real de los artefactos upstream: 19I.18E serializa `results` con `chunk_count` y `redistribution_status`; 19I.18G serializa `technical_conformity_passed`. El error `Campo documents inválido` provenía de asumir un esquema homogéneo entre reportes heterogéneos.


## Hotfix r2

Corrige la ruta real del reporte producido por 19I.18G: `reports/sprint19I18G/runtime_publication_content_conformity.json`. La ruta previa apuntaba a un nombre inexistente. Se agrega prueba de regresión para el contrato de ruta del artefacto.
