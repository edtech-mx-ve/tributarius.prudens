# Sprint 19I.1 — Hotfix local de clasificación de intención

## Problema detectado

La consulta «¿Cuál es la tasa general del IVA y cuál es su fundamento?» fue
clasificada como `related_jurisprudence` por el proveedor mock usado por el
runtime. Esto activó jurisprudencia sin petición expresa y degradó una consulta
fiscal básica.

## Corrección

Se separa el mock de pruebas del runtime y se incorpora
`RuntimeQueryAnalyzerProvider`, clasificador determinista provisional previo a
Sprint 20.

Principios:
- jurisprudencia solo se activa con lenguaje jurisprudencial explícito;
- cálculo ISR/IVA conserva prioridad cuando la consulta pide calcular;
- consultas sobre fundamento, artículo, ley, disposición o vigencia se
  clasifican como `interpret_provision`;
- se añade el hecho `matter=IVA` o `matter=ISR` cuando aparece explícitamente;
- el proveedor sigue siendo determinista, sin red ni servicios comerciales.

## Alcance

Este hotfix corrige clasificación y activación jurisprudencial. No convierte
todavía chunks RAG en candidatos normativos aplicables; por tanto,
`applicable_normative_refs` puede continuar vacío hasta el incremento dedicado
a integración normativa.

## Criterios de aceptación

La consulta de regresión de IVA/fundamento debe producir:
- `primary_intent=interpret_provision`;
- `jurisprudence_requested=false`;
- etapa jurisprudencial `skipped`, no `degraded`;
- RAG 19G operativo;
- sin regresión en Ruff, mypy y pytest.


## Hotfix r2

La primera versión inspeccionaba el `content` completo del mensaje estructurado
generado por `build_query_analysis_messages()`. Ese JSON incluye
`allowed_intents`, por lo que palabras como `calculate_isr` e
`interpret_provision` contaminaban la clasificación.

r2 parsea el JSON de entrada y clasifica exclusivamente el campo `query`. Si el
mensaje no es JSON válido o no contiene ese campo, usa el contenido bruto como
fallback controlado. Se añade una prueba de regresión que verifica que los
metadatos del prompt no alteren la intención.


## Hotfix r3

Corrige exclusivamente la colisión de nombre local detectada por mypy (`payload` redefinido). No modifica la lógica funcional validada por las 6 pruebas de regresión.
