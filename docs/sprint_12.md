# Sprint 12 — CBR (Case-Based Reasoning)

## Objetivo

Incorporar razonamiento basado en casos semejantes como memoria experiencial
complementaria, sin permitir que un caso sustituya normativa vigente, reglas
deterministas o cálculos reproducibles.

El ciclo implementado es:

`Retrieve → Reuse → Revise → Retain`

## Retrieve

La recuperación usa una similitud ponderada explicable sobre:

- tipo de contribuyente: 0.18
- actividad: 0.16
- impuesto: 0.18
- tipo de problema: 0.18
- acto de autoridad: 0.10
- etapa procedimental: 0.10
- ejercicio fiscal: 0.10

La actividad y el tipo de problema usan similitud de Jaccard sobre tokens
normalizados. Los campos categóricos usan coincidencia exacta normalizada.
El ejercicio obtiene 1.0 si coincide, 0.5 con diferencia de un año y 0.0
con mayor distancia. Los campos opcionales ausentes en ambos casos no
aportan artificialmente similitud.

Solo se recuperan estados `ACTIVE` y `HISTORICAL`.
`SUPERSEDED` e `INVALIDATED` quedan excluidos.

## Reuse

Cada coincidencia puede evaluarse frente a las referencias normativas
actualmente aplicables.

- caso ACTIVE + referencia normativa compartida → `ELIGIBLE`;
- caso HISTORICAL → `REVIEW_REQUIRED`;
- caso sin referencias normativas → `REVIEW_REQUIRED`;
- caso sin intersección con normativa vigente → `REVIEW_REQUIRED`;
- caso SUPERSEDED/INVALIDATED → `REJECTED`.

Por tanto, CBR aporta experiencia pero no determina vigencia.

## Revise

La revisión de una solución recuperada exige confirmación humana explícita.
No existe revisión autónoma silenciosa.

## Retain

Un nuevo caso no se activa automáticamente. `create_retention_candidate()`
genera un candidato determinista con estado `PENDING_REVIEW` y conserva el
caso propuesto como histórico hasta que exista un flujo de revisión formal.

## Persistencia

Se añade la migración Alembic `0002_cbr_cases` y el modelo SQLAlchemy
`CBRCaseRecord`. El repositorio funciona con SQLite durante desarrollo y
permanece portable a PostgreSQL.

Los datasets JSONL son entrada/exportación controlada, no sustituto de la
persistencia principal.

## Anonimización

El loader exige que cada caso declare explícitamente:

- `anonymized=true`
- `validated=true`

Además existe un redactor determinista para RFC, CURP y correo electrónico.
Este redactor siempre devuelve `requires_human_review=true`; no se considera
una garantía suficiente de anonimización total.

No deben registrarse secretos, RFC, CURP, correos ni otros datos personales
en logs o repositorios de código.

## Integración con el orquestador

El Sprint 11 se amplía con una etapa `CBR`.

`consulta → RAG → normativa → reglas → cálculo → CBR → Llama`

Los casos similares se incorporan al contexto determinista de Llama, pero
las evaluaciones de reutilización se calculan contra la normativa vigente.
Un caso histórico o normativamente incompatible activa revisión humana.

## Datos de prueba

`cbr/fixtures/cases_test.jsonl` y `query_test.json` contienen únicamente
datos sintéticos. No representan casos fiscales reales ni precedentes.

## Limitaciones

La similitud actual es simbólica y ponderada; todavía no incorpora embeddings
de casos, aprendizaje automático de pesos ni evaluación estadística con un
corpus experto. Los pesos son una línea base explícita que debe calibrarse
posteriormente con casos validados.

La detección de PII es parcial y exige revisión humana. No existe retención
automática desde conversaciones ni extracción autónoma de hechos sensibles.

## Criterios de aceptación

- recuperar casos de forma determinista y explicable;
- excluir `SUPERSEDED` e `INVALIDATED`;
- marcar históricos para revisión;
- impedir reutilización automática cuando no coincide normativa vigente;
- persistir casos anonimizados/validados en SQLite/PostgreSQL mediante ORM;
- impedir auto-retención;
- mantener trazabilidad hasta la explicación LLM;
- Ruff, pytest y mypy sin errores bloqueantes.
