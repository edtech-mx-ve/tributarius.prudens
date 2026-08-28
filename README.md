# Tributarius prudens — Sprint 0

Fundación técnica del sistema híbrido jurídico-fiscal.

## Alcance implementado

- FastAPI con `/health` y documentación OpenAPI.
- Configuración por variables de entorno con Pydantic Settings.
- SQLAlchemy 2 preparado para SQLite local y PostgreSQL cloud.
- Sesiones transaccionales con rollback y cierre seguro.
- Alembic preparado para migraciones.
- Logging centralizado sin contenido fiscal sensible.
- Pruebas automatizadas.
- Ruff y mypy.
- GitHub Actions.
- Base modular para dominio, servicios, API, esquemas y web.

## Decisión de persistencia

Desarrollo local:
`DATABASE_URL=sqlite:///./tributarius.db`

Cloud:
`DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@HOST:5432/BD`

La URL de producción se suministrará mediante variable de entorno y nunca se versionará.

## Ejecutar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
pytest
ruff check .
mypy app
uvicorn app.main:app --reload
```

Abrir:
- API: http://127.0.0.1:8000
- Salud: http://127.0.0.1:8000/health
- Swagger: http://127.0.0.1:8000/docs


## Sprint 1 — Pipeline documental

Procesar un PDF:

```powershell
python -m scripts.process_pdf `
  --input ".\knowledge\sources\normativa\documento.pdf" `
  --source-type normativa
```

Tipos permitidos: `prodecon`, `unam`, `normativa`, `jurisprudencia`.

El PDF original se conserva en `knowledge/sources/`; el corpus operativo queda
en `knowledge/normalized/` y los metadatos trazables en `knowledge/metadata/`.


## Sprint 2 — Modelo de conocimiento

Crear/actualizar esquema local:

```powershell
alembic upgrade head
```

Cargar la Matriz Maestra:

```powershell
python -m scripts.load_master_matrix
```

Consultar:

```text
GET http://127.0.0.1:8000/knowledge/matrix
```

El modelo separa explícitamente PRODECON, UNAM, normativa, jurisprudencia y CBR.
La jurisprudencia permanece como capa independiente y opcional.


## Sprint 3 — Chunking jurídico estructural

```powershell
python -m scripts.chunk_legal_document `
  --markdown ".\knowledge\normalized\normativa\documento.md" `
  --metadata ".\knowledge\metadata\documento.json" `
  --output ".\knowledge\chunks\normativa\documento.jsonl"
```

La salida JSONL conserva jerarquía jurídica, página, procedencia y SHA-256.
Embeddings y FAISS se implementarán en Sprint 4.


## Sprint 4 — Embeddings + FAISS CPU

Construcción del índice:

```powershell
python -m scripts.build_faiss_index `
  --chunks ".\knowledge\chunks\normativa\documento.jsonl" `
  --output-dir ".\indexes\normativa"
```

Verificación de integridad:

```powershell
python -m scripts.verify_vector_index `
  --index-dir ".\indexes\normativa"
```

El índice usa embeddings normalizados y `FAISS IndexFlatIP`. La descarga inicial del
modelo de Sentence Transformers es gratuita; después puede ejecutarse con
`--local-files-only`.


## Sprint 5 — Retriever + evaluación RAG

Búsqueda semántica Top-K con filtros jurídicos:

```powershell
python -m scripts.search_vector_index `
  --index-dir ".\indexes\normativa" `
  --query "obligaciones fiscales" `
  --top-k 5 `
  --source-type normativa `
  --local-files-only
```

Evaluación offline con Recall@K, Precision@K, MRR y Hit Rate:

```powershell
python -m scripts.evaluate_retrieval `
  --index-dir ".\indexes\normativa" `
  --dataset ".\rag\evaluation\datasets\normativa_eval.jsonl" `
  --k 5 `
  --local-files-only
```


## Sprint 6 — Integración de Llama

La capa LLM ya consume evidencia recuperada y exige una salida JSON validada. Para una
prueba sin modelo real:

```powershell
python -m scripts.explain_with_llama `
  --index-dir ".\indexes\normativa" `
  --query "¿Qué obligaciones están respaldadas por la evidencia?" `
  --provider mock `
  --embedding-local-files-only
```

El backend GGUF local es opcional:

```powershell
pip install -e ".[llama]"
```

No se usan APIs comerciales ni claves.


## Sprint 7 — Query Analyzer

El sistema incorpora una etapa previa de análisis estructurado de la consulta:

```text
consulta → normalización → intent/facts/entities/missing data → validación
```

Prueba offline:

```powershell
python -m scripts.analyze_query `
  --query "Quiero calcular ISR" `
  --provider mock
```

El analizador no sustituye normativa, reglas ni cálculos.


## Sprint 8 — Motor normativo y vigencia temporal

Se incorpora una capa determinista para resolver aplicabilidad temporal de versiones normativas por fecha y ejercicio fiscal. La vigencia no se delega al LLM.


## Sprint 9 — Motor de reglas

Inferencia simbólica determinista, versionada y trazable, con dependencia explícita de normas aplicables.


## Sprint 10 — Cálculo determinista de ISR

Se incorpora un núcleo monetario reproducible con Decimal, tarifa versionada, referencia normativa obligatoria y trazabilidad paso a paso. La tarifa incluida es únicamente una fixture sintética de pruebas.


## Sprint 11 — Orquestador híbrido

Conecta Query Analyzer, RAG, validación normativa, reglas, ISR y explicación LLM mediante contratos tipados, trazabilidad por etapa y degradación controlada.


## Sprint 12 — Case-Based Reasoning

Se incorpora CBR explicable con similitud ponderada, estados de ciclo de vida, persistencia SQLAlchemy/Alembic, controles de anonimización, revisión normativa antes de reutilizar y retención únicamente mediante candidato pendiente.


## Sprint 13 — Trazabilidad integral

Se añade un resultado canónico con folio, eventos por etapa, referencias de evidencia, incertidumbre, revisión humana, huellas SHA-256, exportación JSON controlada y verificación de integridad.


## Sprint 14 — Interfaz web

Interfaz FastAPI/Jinja2 responsiva y accesible, con HTML semántico, CSS móvil primero, JavaScript mínimo, validación cliente/servidor y presenter de `CanonicalExecutionResult`. El endpoint declara `not_configured` si el runtime fiscal real no está conectado, evitando respuestas simuladas.


## Sprint 15 — Seguridad y robustez

Se endurece la frontera HTTP con Trusted Hosts, límites de cuerpo, CSP y headers
de seguridad, same-origin, rate limiting acotado, errores sin eco de entradas,
normalización segura, señales de prompt injection y redacción adicional de
secretos en logs. La documentación automática se deshabilita en producción y
HSTS se activa únicamente bajo HTTPS de producción.


## Sprint 16 — Evaluación integral

Se añade una capa offline reproducible sobre `CanonicalExecutionResult` para
medir intención, RAG, citas, normativa, reglas, cálculos, revisión humana,
abstención y consistencia de trazabilidad, con umbrales explícitos, SHA-256 del
dataset, análisis de errores y reporte JSON.


## Sprint 17 — Marco jurisprudencial

Se incorpora una capa jurisprudencial separada y opcional con contratos
tipados, metadatos JSONL validados, política de activación, estados
operacionales, relación explícita con normativa, retriever aislado,
trazabilidad independiente y métricas para relevancia, relación normativa y
recuperación espuria. El razonamiento normativo-jurisprudencial conjunto se
reserva para Sprint 18.


## Sprint 18 — Razonamiento normativo-jurisprudencial

El orquestador integra ahora jurisprudencia después de validar la normativa,
con recuperación separada, degradación segura, revisión humana, contexto
estructurado para Llama y `jurisprudential_sources` independiente en la
trazabilidad canónica. Jurisprudencia no modifica vigencia normativa, reglas
ni cálculos.


## Sprint 19 — Despliegue Render

Infraestructura como código en `render.yaml`, perfil gratuito y efímero, `/ready`, validación de despliegue, CI ampliado y smoke HTTP remoto. Véase `docs/sprint_19.md`.


## Publicación segura en GitHub

Antes de publicar, ejecutar `python -m scripts.audit_github_publish` y revisar
`docs/github_publication.md`. El repositorio excluye secretos, datos reales,
corpus operativo, bases locales, índices FAISS, pesos de modelos y artefactos
de ejecución.
