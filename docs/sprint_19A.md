# Sprint 19A — Integración PRODECON

## Objetivo

Convertir `PRODECON Contribuyente.pdf` en una fuente operacional local estructurada en
12 apartados, sin publicar el PDF ni el texto derivado en GitHub.

## Decisiones

- El PDF original permanece como evidencia.
- La salida normalizada y los apartados derivados permanecen fuera del repositorio público.
- `knowledge/metadata/prodecon_12_mapping.json` sí puede versionarse: contiene estructura,
  páginas y vínculo funcional, no el contenido completo del documento.
- Cada apartado conserva páginas, módulo funcional, hash y trazabilidad al SHA-256 del PDF.
- La integración falla si no existen exactamente 12 apartados o si el documento no es PRODECON.
- No se sobrescriben artefactos existentes salvo `--overwrite`.

## Implementación

Con el entorno virtual activo desde la raíz del proyecto:

```powershell
python -m scripts.integrate_prodecon `
  --pdf "RUTA\PRODECON Contribuyente.pdf"
```

Resultado esperado:

```text
OK: PRODECON integrado; ... apartados=12; sha256=...
```

Artefactos locales:

```text
knowledge/normalized/prodecon/prodecon-contribuyente.md
knowledge/normalized/prodecon/sections/prodecon-01.md ... prodecon-12.md
knowledge/metadata/prodecon-contribuyente.json
knowledge/metadata/prodecon_integration_manifest.json
```

Validación:

```powershell
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
python -m scripts.audit_github_publish
```

## Criterios de aceptación

1. Se detectan exactamente 12 apartados.
2. Cada apartado conserva su rango de páginas.
3. Cada apartado está ligado a un módulo funcional.
4. Se generan hashes SHA-256 de cada apartado.
5. El manifiesto conserva el SHA-256 del PDF fuente.
6. No se publica contenido derivado del corpus por defecto.
7. Ruff, mypy y pytest permanecen verdes.

## Limitaciones

- Los rangos de páginas corresponden a esta edición concreta de PRODECON.
- Este sprint estructura PRODECON; la indexación FAISS productiva se realizará en 19E.
- No se interpreta PRODECON como norma jurídica vinculante.
