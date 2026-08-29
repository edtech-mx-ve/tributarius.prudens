# Sprint 19B — Integración local del corpus fiscal restante

## Objetivo

Ingerir localmente los 15 PDF restantes del corpus de Tributarius prudens, conservando
PRODECON como resultado del Sprint 19A. Este sprint produce Markdown normalizado,
metadatos documentales, metadatos jurídicos laterales y un manifiesto integral de los
15 documentos.

No construye todavía embeddings ni el índice FAISS; eso corresponde al siguiente
incremento del Sprint 19.

## Entrada esperada

Directorio externo local con estos 16 PDF:

- CFF.pdf
- CPEUM.pdf
- LFDC.pdf
- LFISAN.pdf
- LFPCA.pdf
- LIEPS.pdf
- LIF_2026.pdf
- LISR.pdf
- LIVA.pdf
- LOTFJA.pdf
- Manual Derecho Fiscal.pdf
- PRODECON Contribuyente.pdf
- Reg_CFF.pdf
- Reg_LISR_060516.pdf
- Reg_LIVA_250914.pdf
- SHCP_281225_01.pdf

Sprint 19B procesa 15; PRODECON ya fue procesado por Sprint 19A.

## Salidas

- `knowledge/normalized/unam/*.md`
- `knowledge/normalized/normativa/*.md`
- `knowledge/metadata/*.json`
- `knowledge/metadata/legal/*.json`
- `knowledge/metadata/fiscal_corpus_15_manifest.json`

Los PDF originales permanecen fuera del repositorio.

## Implementación local

```powershell
python -m scripts.integrate_fiscal_corpus `
  --corpus-dir "D:\DISCO C\Antonio Toro\Proyectos_IA\Tributarius_Prudens\Corpus app"
```

Para una regeneración deliberada:

```powershell
python -m scripts.integrate_fiscal_corpus `
  --corpus-dir "D:\DISCO C\Antonio Toro\Proyectos_IA\Tributarius_Prudens\Corpus app" `
  --overwrite
```

## Criterios de aceptación

1. Catálogo válido de exactamente 15 documentos.
2. Preflight rechaza cualquier PDF requerido ausente.
3. UNAM se conserva como doctrina, no como normativa.
4. Los 14 documentos jurídicos restantes se clasifican como normativa.
5. Cada documento genera Markdown y metadatos con SHA-256.
6. Se genera un manifiesto de 15 documentos.
7. Ruff, mypy y pytest permanecen limpios.
8. Todo se valida en local antes de GitHub o Render.

## Limitaciones

- La extracción depende de texto embebido en los PDF; no se incorpora OCR.
- Las fechas del catálogo describen la versión documental conocida, no sustituyen un
  motor de vigencia normativa por unidad.
- La segmentación jurídica fina por artículo/regla/capítulo y el índice FAISS se
  implementan después de validar esta ingestión.
- No se publican PDF ni corpus derivados sin revisión de licencias y política de
  publicación.
