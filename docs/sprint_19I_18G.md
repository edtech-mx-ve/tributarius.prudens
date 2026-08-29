# Sprint 19I.18G — auditoría local de conformidad del contenido

Objetivo: auditar los 14 documentos normativos candidatos del runtime semántico
v2 sin convertir una clasificación técnica en una autorización jurídica.

La auditoría verifica:

- cobertura de los 14 `document_id`;
- `source_type=normativa`;
- `source_role` esperado por documento;
- una identidad `source_sha256` coherente por documento;
- integridad del texto cuando existe `retrieval_text_sha256`;
- marcadores editoriales conservadores que disparan revisión manual.

`publication_promotion_allowed` permanece siempre en `False`. Un resultado
técnicamente conforme solo habilita el siguiente paso de revisión de evidencia;
no autoriza un release público.

## Implementación

```powershell
pytest tests/test_runtime_publication_content_audit_19i18g.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_runtime_publication_content_19i18g
python -m scripts.audit_runtime_publication_safety_19i18e
$LASTEXITCODE
```

El auditor de seguridad 19I.18E debe continuar bloqueando la publicación con
código de salida 3.
