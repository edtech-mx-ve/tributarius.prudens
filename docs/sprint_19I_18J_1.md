# Sprint 19I.18J.1 — robustecimiento de descarga oficial

El resultado real de 19I.18J verificó `rmf_2026` por SHA-256 exacto y mostró
13 documentos de Cámara de Diputados con `remote_hashes=0` y `fetch_errors=1`.
Eso significa que el bloqueo ocurrió antes de comparar hashes: no es evidencia
de contenido distinto.

Este incremento:

1. mantiene la política fail-closed;
2. usa perfiles HTTP conservadores, incluido un perfil tipo navegador;
3. añade `Accept-Encoding: identity` para evitar transformar el flujo binario;
4. revalida el host final tras redirects;
5. conserva timeout, límite de tamaño y firma `%PDF-`;
6. registra detalle de HTTP/URL/timeout por intento;
7. corrige las URLs exactas versionadas de:
   - `Reg_LISR_060516.pdf`
   - `Reg_LIVA_250914.pdf`

No se promueve ningún derecho de redistribución.

## Implementación

```powershell
pytest tests/test_runtime_official_source_audit_19i18j.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest

python -m scripts.audit_runtime_official_source_19i18j
python -m scripts.report_official_fetch_errors_19i18j1

python -m scripts.audit_runtime_publication_safety_19i18e
$LASTEXITCODE
```

El código final del safety gate debe continuar siendo 3.
