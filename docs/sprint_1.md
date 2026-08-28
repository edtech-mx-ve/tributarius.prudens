# Sprint 1 — Pipeline documental

## Objetivo

Implementar un pipeline reproducible y auditable para convertir documentos PDF en
Markdown normalizado y metadatos JSON, manteniendo siempre el PDF original como
fuente de evidencia.

## Flujo implementado

PDF original → validación → SHA-256 → extracción por página → limpieza →
detección estructural → Markdown → metadatos JSON → validación.

## Decisiones

- `pypdf` realiza extracción de texto sin servicios externos.
- El pipeline no ejecuta OCR automáticamente.
- Cada página queda marcada en Markdown mediante `<!-- page:n -->`.
- Se conservan por separado fuentes PRODECON, UNAM, normativa y jurisprudencia.
- El PDF original no se modifica.
- No se sobrescriben salidas existentes.
- Cada documento recibe un identificador estable derivado de tipo de fuente + SHA-256.
- Los metadatos guardan extractor, versión, páginas, caracteres, páginas vacías,
  encabezados detectados, checksum y advertencias.

## Criterios de aceptación

1. Rechaza archivos inexistentes, no PDF, vacíos y excesivamente grandes.
2. Extrae texto página por página.
3. Normaliza espacios sin destruir el orden del contenido.
4. Reconoce encabezados jurídicos frecuentes.
5. Produce Markdown UTF-8 con marcadores de página.
6. Produce JSON validado con Pydantic.
7. No sobrescribe salidas previas.
8. Registra advertencias cuando hay páginas sin texto.
9. Mantiene pruebas automatizadas.
10. No depende de APIs comerciales ni servicios externos.

## Limitaciones

- PDFs escaneados sin capa de texto requieren OCR y se reportan como no extraíbles.
- La detección de estructura es heurística; el chunking jurídico especializado se
  implementará en Sprint 3.
- No se hacen todavía embeddings ni FAISS.
- No se decide vigencia normativa; corresponde al motor normativo posterior.

## Ejemplo

```powershell
python -m scripts.process_pdf `
  --input ".\knowledge\sources\normativa\documento.pdf" `
  --source-type normativa
```

Resultado esperado:

```text
knowledge/
├── sources/normativa/documento.pdf
├── normalized/normativa/documento.md
└── metadata/documento.json
```
