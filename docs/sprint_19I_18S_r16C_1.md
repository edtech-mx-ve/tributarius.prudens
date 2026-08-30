# Sprint 19I.18S-r16C.1 — Activación de Trace Integrity

Conecta `reconcile_traceability_payload` a la misma frontera JSON ya usada para
normalización Unicode.

Orden deliberado:

1. parseo JSON;
2. reconciliación de trazabilidad;
3. normalización Unicode;
4. serialización UTF-8.

La reconciliación sólo cambia presentación/trazabilidad cuando el resultado
global ya exige revisión, existe evidencia normativa y no hay referencias
aplicables. No cambia reglas, aplicabilidad, cálculos, recuperación ni decisión
jurídica.

## Gate

Después de los tests focalizados debe ejecutarse el smoke local IVA. El evento
`normative` debe pasar a `requires_human_review=True` y explicar la abstención,
manteniendo cero refs aplicables y backend lexical_cpu.
