# Sprint 19 — Despliegue Render

## Objetivo

Preparar un despliegue reproducible y verificable de Tributarius prudens en un
Render Web Service gratuito, manteniendo el runtime sin dependencias de pago,
sin disco persistente y sin almacenar secretos en el repositorio.

## Arquitectura de despliegue

```text
GitHub
  -> GitHub Actions
      -> Ruff
      -> mypy
      -> pytest
      -> validación render.yaml
      -> smoke normativo-jurisprudencial
  -> Render Blueprint
      -> Python 3.12
      -> pip install -e .
      -> Uvicorn
      -> FastAPI
      -> /health
      -> /ready
      -> interfaz web
```

## Perfil gratuito

`render.yaml` declara explícitamente:

- `type: web`
- `runtime: python`
- `plan: free`
- `autoDeployTrigger: checksPass`
- `healthCheckPath: /health`
- un único worker Uvicorn;
- base SQLite efímera en `/tmp`;
- sin Postgres gestionado;
- sin disco persistente;
- sin secretos embebidos.

La base SQLite del perfil `stateless_free` es deliberadamente efímera. No debe
usarse como almacenamiento legal, fiscal o de casos a largo plazo.

## Python

`.python-version` contiene `3.12`, para evitar depender del Python por defecto
del proveedor y mantener alineación con el proyecto.

## Salud y readiness

`GET /health` comprueba que el proceso y la conectividad SQL básica están
operativos. Es la ruta utilizada por Render para decidir salud HTTP.

`GET /ready` reporta capacidades de runtime:

- base de datos;
- artefactos RAG.

Si los artefactos RAG son opcionales y faltan, el estado es `degraded`. Si se
configura `REQUIRE_RAG_ARTIFACTS=true`, su ausencia produce `503 not_ready`.

## Artefactos RAG

Render no genera embeddings ni construye FAISS durante el arranque. La
construcción pesada se mantiene fuera del runtime. El contrato de artefactos
espera:

- `index.faiss`
- `chunks.jsonl`
- `manifest.json`

en `deployment/runtime_artifacts`.

El perfil actual conserva `REQUIRE_RAG_ARTIFACTS=false` porque el runtime web
debe arrancar sin simular respuestas fiscales cuando el motor completo aún no
está provisionado.

## CI

`.github/workflows/ci.yml` ejecuta:

```text
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.validate_deployment
python -m scripts.smoke_normative_jurisprudential
```

Render usa `checksPass`, de modo que los commits deben superar los controles
antes del auto-deploy.

## Validación local

```powershell
python -m scripts.validate_deployment
python -m scripts.smoke_normative_jurisprudential
```

## Smoke remoto

Después del primer deploy:

```powershell
python -m scripts.smoke_remote --base-url "https://tributarius-prudens.onrender.com"
```

El comando admite el cold start del plan gratuito con timeout de 90 segundos.

## Seguridad

- `ENVIRONMENT=production`.
- Swagger/ReDoc deshabilitados.
- HSTS activado por el middleware existente.
- `TrustedHostMiddleware` limitado a hosts `onrender.com` para el blueprint.
- tamaño de request y rate limit conservados.
- no se incluyen claves API ni credenciales.
- no se crea base PostgreSQL temporal que expire y pueda confundirse con
  persistencia durable.

## Limitaciones

- El filesystem del servicio gratuito es efímero.
- SQLite en `/tmp` se pierde con reinicios, redeploys y spin-down.
- El servicio gratuito puede entrar en reposo y sufrir cold start.
- El perfil no pretende alta disponibilidad ni producción crítica.
- Los artefactos RAG reales no se incluyen en este sprint.
- Un Llama local de tamaño significativo no se carga en este perfil gratuito.
- El runtime web continúa sin inventar respuestas si el motor de consulta no
  está configurado.
- El dominio Render exacto debe confirmarse tras crear el servicio.

## Criterios de aceptación

- `render.yaml` validado.
- plan explícitamente `free`.
- sin base de datos o disco gestionado de pago.
- Python 3.12 fijado.
- `/health` operativo.
- `/ready` operativo.
- CI ampliado.
- smoke normativo-jurisprudencial intacto.
- smoke remoto preparado.
- Ruff, pytest y mypy limpios en el entorno local del proyecto.
