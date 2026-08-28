# Sprint 2 — Modelo de conocimiento y Matriz Maestra Jurídico-Fiscal

## Objetivo

Representar de forma persistente y portable las fuentes, unidades jurídicas, versiones
temporales, relaciones y el mapa funcional que conecta conocimiento con reglas,
cálculos y CBR.

## Modelo implementado

- `knowledge_sources`: procedencia y capa.
- `legal_units`: documento/título/capítulo/sección/artículo/fracción/inciso/criterio/caso.
- `norm_versions`: versión, publicación, vigencia y ejercicio fiscal.
- `knowledge_relations`: relaciones explícitas entre unidades.
- `master_matrix_entries`: módulo ↔ PRODECON ↔ UNAM ↔ normativa ↔ jurisprudencia
  opcional ↔ reglas ↔ cálculos ↔ CBR.

## Principios

1. Jurisprudencia y normativa no se mezclan.
2. La vigencia temporal es dato explícito, no inferencia del LLM.
3. Las referencias aún no documentadas se marcan como `por_mapear`; no se inventan.
4. JSON de la matriz es editable y auditable; SQL es la persistencia operacional.
5. SQLAlchemy mantiene compatibilidad SQLite/PostgreSQL.
6. Alembic controla evolución del esquema.
7. La matriz se carga mediante upsert por `module_key`, por lo que el proceso es idempotente.

## Seguridad y robustez

- Pydantic valida estructura y periodos de vigencia.
- Relaciones inválidas fallan explícitamente.
- No hay secretos ni datos fiscales personales.
- No se usa SQL específico de PostgreSQL.
- La API devuelve error controlado si la base no está disponible.

## Criterios de aceptación

- Migración crea las cinco estructuras persistentes.
- El dominio valida fechas y claves.
- El repositorio persiste fuentes, unidades, versiones y relaciones.
- La matriz inicial se valida desde JSON.
- La carga puede repetirse sin duplicar módulos.
- `GET /knowledge/matrix` expone la matriz persistida.
- Pruebas unitarias cubren dominio, repositorio y carga.
- El Sprint 1 continúa funcionando.

## Limitaciones

- Las referencias `por_mapear` son marcadores deliberados hasta procesar corpus reales.
- No se ha implementado todavía chunking jurídico (Sprint 3).
- No hay embeddings/FAISS (Sprint 4).
- El motor de vigencia aplicable será posterior.
- La jurisprudencia se modela, pero su ingestión especializada corresponde a Sprint 17.
