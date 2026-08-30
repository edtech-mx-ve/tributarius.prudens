# Sprint 19I.18S-r15 — Normative Applicability & Response Integrity

## Objetivo

Endurecer el runtime público después de la batería E2E en Render Free. Este incremento no cambia el backend CPU-only ni el artefacto público r10.

## Cambios

- Gate de pertinencia material antes de promover candidatos normativos.
- La vigencia temporal deja de ser criterio suficiente de promoción.
- Las reglas especiales de RMF exigen contexto material específico de la consulta.
- El `fiscal_year` estructurado del request se integra al análisis y elimina falsos faltantes.
- Las instrucciones adversas para omitir evidencia, inventar reglas o saltar temporalidad fuerzan revisión humana.
- Consultas de tasa de IVA se clasifican con intención específica.
- La presentación recupera `summary`/`analysis` del contrato real de explicación.
- Evidencia pública deduplicada por `ref_id`.
- Reparación visual conservadora de mojibake UTF-8 cuando la conversión es reversible.

## Invariantes

1. Temporalmente válida no implica materialmente aplicable.
2. Una RMF específica no sustituye una ley pertinente solo porque tenga fechas conocidas.
3. Si existe evidencia material pero ninguna referencia puede promoverse, se fuerza revisión.
4. Los campos estructurados del request prevalecen sobre falsos faltantes derivados del texto.
5. Las instrucciones del usuario nunca pueden desactivar evidencia, temporalidad ni trazabilidad.
6. El backend Render continúa `lexical_cpu`; este sprint no reintroduce embeddings/FAISS en el request path.

## Pruebas focalizadas

```powershell
python -m pytest tests/test_response_integrity_19s_r15.py -q
python -m ruff check app/services/hybrid_orchestrator.py app/web/presenter.py llm/providers/runtime_query.py tests/test_response_integrity_19s_r15.py
python -m mypy app/services/hybrid_orchestrator.py app/web/presenter.py llm/providers/runtime_query.py
```

## Criterios de aceptación

- Derechos del contribuyente: LFDC puede mantenerse como evidencia; RMF de marbetes/marco contable no se promueve por temporalidad.
- IVA genérico 2026: reglas RMF de buques, misiones diplomáticas o transporte internacional no se promueven sin contexto correspondiente.
- ISR con `fiscal_year=2026`: no reporta `fiscal_year` como faltante.
- Prompt adverso: `requires_human_review=true`.
- `explanation` pública no es `null` cuando el mock produce un `summary`.
- Evidencia no duplica el mismo `ref_id`.
- Sin cambios de infraestructura ni de artefacto r10.

## Implementación

Desde la raíz del repositorio, con `.venv` activa:

```powershell
Expand-Archive `
  -Path .\tributarius-prudens-sprint19I.18S-r15.zip `
  -DestinationPath . `
  -Force

python -m pytest tests/test_response_integrity_19s_r15.py -q
python -m ruff check app/services/hybrid_orchestrator.py app/web/presenter.py llm/providers/runtime_query.py tests/test_response_integrity_19s_r15.py
python -m mypy app/services/hybrid_orchestrator.py app/web/presenter.py llm/providers/runtime_query.py
git diff --check
```

Si lo anterior pasa, ejecutar la regresión local del runtime y después la suite integral. No hacer `git push` ni deploy a Render antes del cierre local del incremento.
