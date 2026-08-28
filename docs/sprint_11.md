# Sprint 11 — Orquestador híbrido

## Objetivo

Conectar en un flujo controlado el Query Analyzer, recuperación RAG, validación
normativa, motor de reglas, cálculo determinista de ISR y explicación con Llama.

## Flujo

`consulta → Query Analyzer → RAG → normativa → reglas → ISR → contexto determinista → Llama`

El orquestador no transfiere autoridad de cálculo o vigencia al LLM. La explicación
recibe evidencia documental más una representación explícita de resultados
deterministas.

## Controles

- jurisprudencia excluida por defecto del retrieval;
- jurisprudencia habilitada solo por solicitud/intención explícita;
- una regla dependiente de norma requiere una referencia aplicable;
- ISR se bloquea si falta información, tarifa o referencia normativa aplicable;
- los cálculos siguen utilizando Decimal;
- si Llama falla, los resultados deterministas se conservan y el estado queda degradado;
- cada etapa produce una traza completed/skipped/degraded.

## Limitaciones

La asociación automática entre un chunk normativo recuperado y `legal_unit_id` todavía
requiere metadatos jurídicos más ricos. Por eso este sprint recibe candidatos normativos
estructurados y aplica el motor temporal sobre ellos. La resolución automática completa
entre retrieval y repositorio normativo se abordará al robustecer el modelo jurídico.

LlamaIndex Core sigue siendo parte de la arquitectura RAG objetivo, pero no se introduce
como dependencia de ejecución del orquestador en este sprint: el contrato `RetrieverLike`
mantiene el servicio desacoplado del backend de recuperación y permite conectar el
adaptador correspondiente sin cambiar la lógica de negocio.
