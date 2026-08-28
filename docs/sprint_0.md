# Sprint 0 — Fundación técnica

## Objetivo
Construir una base ejecutable y comprobable para Tributarius prudens antes de incorporar
corpus, RAG, Llama, normativa, reglas, cálculos y CBR.

## Supuestos
1. Python 3.12+.
2. SQLite para desarrollo local.
3. PostgreSQL para cloud cuando se seleccione un proveedor que cumpla costo $0 y sin tarjeta.
4. Sin autenticación en este sprint; no se procesan todavía datos fiscales reales.
5. No se integra Llama ni RAG en Sprint 0.

## Criterios de aceptación
- La aplicación inicia mediante Uvicorn.
- GET /health responde HTTP 200.
- El endpoint comprueba conectividad real con la base.
- La misma capa SQLAlchemy permite cambiar SQLite por PostgreSQL mediante DATABASE_URL.
- La configuración no contiene secretos.
- pytest, ruff y mypy forman parte del contrato de calidad.
- Existe pipeline CI para cada push/pull request.

## Limitaciones
- No hay modelos de dominio fiscal todavía.
- No hay persistencia CBR todavía.
- No hay interfaz web de usuario.
- No hay autenticación.
- No hay despliegue cloud todavía.

## Próximo sprint
Sprint 1: pipeline documental PDF → extracción → limpieza → Markdown normalizado → metadata → validación.
