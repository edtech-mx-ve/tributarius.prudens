# Sprint 13 — Trazabilidad integral

## Objetivo

Construir un registro canónico, verificable y desacoplado de la interfaz para
representar una ejecución completa de Tributarius prudens. El resultado puede
alimentar posteriormente API, HTML, PDF, DOCX y auditoría sin volver a ejecutar
el razonamiento.

## Identidad de ejecución

Cada ejecución trazada recibe:

- `execution_id`: identificador aleatorio UUID4 representado como `TP-...`;
- `folio`: `TP-AAAAMMDD-XXXXXXXXXXXX`;
- `created_at_utc`: fecha/hora UTC;
- `query_sha256`: huella de la consulta, sin copiar la consulta al registro de
  auditoría.

La consulta sí puede existir dentro del resultado funcional canónico porque el
Query Analyzer la conserva. Por seguridad, ese resultado no se registra ni
persiste automáticamente.

## Eventos

Las etapas del orquestador se convierten en eventos secuenciales con:

- número de secuencia;
- etapa;
- estado;
- resumen controlado;
- referencias de evidencia;
- indicador de revisión humana.

Los estados son `COMPLETED`, `SKIPPED`, `DEGRADED` y `REVIEW_REQUIRED`.

## Evidencia

La trazabilidad diferencia explícitamente:

- documentos recuperados;
- normativa;
- reglas;
- cálculos;
- casos CBR;
- explicación LLM.

Las referencias conservan identificadores, versión, ejercicio, fuente y score
cuando corresponda. No se almacena el texto completo de los chunks en el
registro de auditoría.

## Incertidumbre

Se materializan como objetos trazables:

- campos faltantes;
- ambigüedades;
- normativa no aplicable o incierta;
- reutilización CBR que requiere revisión;
- explicación LLM no disponible.

La revisión humana se conserva tanto a nivel de evento como de resultado.

## Resultado canónico

`CanonicalExecutionResult` contiene:

`query_analysis + retrieval + normative + rules + calculations + cbr +
explanation + uncertainty + traceability`

Este objeto es la frontera entre razonamiento y presentación. Los futuros
renderers HTML/PDF/DOCX deben consumirlo en lugar de volver a ejecutar Llama,
reglas o cálculos.

## Integridad

El contenido funcional canónico recibe una huella SHA-256. La huella excluye
su propio campo para evitar autorreferencia. `verify_canonical_integrity()`
permite detectar alteraciones posteriores en resultados, cálculos, fuentes,
CBR o explicación.

Esto detecta cambios accidentales o no autorizados, pero no sustituye firma
digital, sellado de tiempo confiable ni controles criptográficos de identidad.

## Exportación

La exportación JSON:

- es explícita;
- usa UTF-8;
- no sobrescribe por defecto;
- escribe primero un temporal y luego reemplaza el destino;
- no ocurre automáticamente durante una consulta.

El archivo canónico puede contener datos de la consulta y debe tratarse como
información potencialmente sensible.

## Fixture

`traceability/fixtures/trace_test.json` es completamente sintético y sirve
solo para probar carga e integridad.

## Limitaciones

No existe todavía persistencia automática de auditoría, firma digital,
cifrado de archivos, control de acceso por usuario ni política de retención.
Estas decisiones deben definirse antes de almacenar consultas fiscales reales.

La trazabilidad registra evidencia y decisiones observables; no almacena ni
expone razonamiento interno privado del modelo.

## Criterios de aceptación

- folio e identificador únicos;
- secuencia de eventos por etapa;
- referencias de evidencia separadas por tipo;
- incertidumbre y revisión humana explícitas;
- consulta ausente del registro de auditoría salvo huella SHA-256;
- resultado canónico serializable;
- verificación de integridad;
- exportación sin sobrescritura silenciosa;
- pruebas y verificación estática sin errores bloqueantes.
