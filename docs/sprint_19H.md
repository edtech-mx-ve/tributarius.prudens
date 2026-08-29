# Sprint 19H — Integración RAG end-to-end

## Objetivo

Conectar el retrieval jurídico 19G al runtime web real sin reconstruir FAISS ni
duplicar razonamiento fiscal.

## Implementación

Flujo:

`POST /api/v1/consultations -> WebConsultationService -> WebHybridRunner ->
HybridOrchestrator -> LegalHybridRetriever 19G -> FAISS 19F -> trazabilidad ->
presentador web`.

El runtime carga `manifest.json`, usa el mismo modelo de embeddings declarado por
el índice, verifica hashes por defecto y aplica la política jurídica
`app/resources/legal_retrieval_policy.json`.

Hasta Sprint 20, el análisis de intención y la explicación usan proveedores mock
deterministas ya existentes. No se presentan como razonamiento Llama de
producción. El retrieval y la evidencia documental sí son reales.

Si faltan artefactos o configuración, la aplicación conserva `not_configured` y
`/ready` queda degradado o no listo según `REQUIRE_RAG_ARTIFACTS`.

## Seguridad y robustez

- Validación de archivos requeridos y manifest.
- Verificación SHA-256 del índice/chunks por defecto.
- CPU solamente.
- `local_files_only` configurable.
- Sin secretos en configuración ni logs.
- Degradación cerrada: no se simula una respuesta fiscal si el runtime no carga.
- Los documentos recuperados siguen tratándose como evidencia, no instrucciones.

## Limitaciones

El Sprint 19H no incorpora todavía Llama real ni convierte automáticamente chunks
recuperados en candidatos normativos versionados del motor de aplicabilidad.
Eso corresponde a incrementos posteriores; 19H demuestra integración RAG real
end-to-end en la aplicación.

## Criterios de aceptación

1. Ruff, mypy y pytest completos limpios.
2. Con artefactos 19F presentes, el runtime se construye.
3. El smoke local devuelve evidencia documental real.
4. El retrieval empleado es `legal_hybrid_19g`.
5. Sin artefactos, la web no inventa respuesta y mantiene degradación segura.
6. No se reconstruyen embeddings ni FAISS.

## Implementación local

```powershell
pytest tests/test_runtime_factory_19h.py tests/test_web_runtime_runner_19h.py tests/test_web_dependencies_19h.py -v
ruff check . --fix
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest

python -m scripts.smoke_local_19h `
  --index-dir ".\deployment\runtime_artifacts_19f" `
  --local-files-only
```

Resultado esperado: pruebas limpias y mensaje `OK: integración 19H operativa`.
