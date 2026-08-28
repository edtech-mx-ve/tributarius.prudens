# Publicación segura en GitHub

## Objetivo

Publicar únicamente código, configuración reproducible, documentación y
fixtures sintéticos. El repositorio público no debe contener secretos, datos
fiscales reales, expedientes, corpus jurídico-fiscal sin revisión de licencia,
artefactos RAG generados, bases locales ni pesos de modelos.

## Sí se publica

- `app/`, `rag/`, `llm/`, `rules/`, `calculators/`, `cbr/` (código y fixtures sintéticos).
- `jurisprudence/` (código y fixture explícitamente sintético).
- `evaluation/` (código y dataset smoke sintético).
- `tests/`, `scripts/`, `docs/`.
- `migrations/`.
- `render.yaml`, `.python-version`, `pyproject.toml`.
- `.env.example`, nunca `.env`.
- `knowledge/metadata/master_matrix.json`.
- `.gitkeep` que preserve carpetas vacías.
- interfaz web y recursos estáticos propios del proyecto.

## No se publica

- `.venv`, caches, bytecode, logs y reportes generados.
- `.env`, llaves, certificados, credenciales y tokens.
- SQLite/PostgreSQL dumps o cualquier base local.
- PDFs originales y otros archivos de `knowledge/sources/`.
- Markdown normalizado de `knowledge/normalized/` hasta revisar licencia.
- chunks operativos de `knowledge/chunks/`.
- índices FAISS y runtime artifacts reales.
- modelos GGUF, SafeTensors, PyTorch, ONNX o caches Hugging Face.
- exportaciones de trazabilidad.
- casos CBR reales, datos de contribuyentes o expedientes.
- ZIPs y paquetes locales.
- rutas absolutas de usuarios/equipos.

## Preflight obligatorio

Antes de `git add .`:

```powershell
python -m scripts.audit_github_publish
git status --short
git status --ignored --short
```

El auditor usa los candidatos de `git ls-files --cached --others
--exclude-standard`, por lo que comprueba tanto lo ya rastreado como lo nuevo
que no esté ignorado.

Si un archivo sensible ya fue rastreado antes de añadirlo a `.gitignore`,
`.gitignore` no lo elimina del índice. Debe retirarse de Git sin borrar el
archivo local:

```powershell
git rm --cached "RUTA"
```

Para una carpeta:

```powershell
git rm -r --cached "RUTA"
```

Después se vuelve a ejecutar el auditor.

## Revisión del staging

Solo cuando el preflight termine en `OK`:

```powershell
git add .
git status --short
git diff --cached --stat
git diff --cached -- . ":(exclude)*.lock"
python -m scripts.audit_github_publish
```

No hacer `git push` hasta revisar el staging.

## Secretos históricos

Si alguna credencial real ya fue confirmada en commits previos, quitarla del
working tree no basta: debe revocarse/rotarse y limpiarse del historial antes
de publicar. Este documento no automatiza una reescritura destructiva del
historial.
