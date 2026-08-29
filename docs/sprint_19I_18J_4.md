# Sprint 19I.18J.4 — gate jurídico normativo de redistribución

## Objetivo

Separar la **base jurídica candidata** de la **decisión operativa de publicar**.

Fuentes oficiales verificadas para este incremento:

1. Ley Federal del Derecho de Autor, artículo 14, fracción VIII:
   `https://www.diputados.gob.mx/LeyesBiblio/pdf/LFDA.pdf`
2. Aviso Legal del Diario Oficial de la Federación:
   `https://dof.gob.mx/aviso_legal.html`

El gate conserva `automatic_publication_promotion=False`.

## Regla técnica

Un documento normativo solo puede clasificarse como
`legal_basis_candidate_supported_pending_redistribution_review` cuando:

- 19I.18F lo clasifica como `statutory_text_exclusion_candidate`;
- 19I.18G acredita conformidad técnica;
- 19I.18I acredita runtime -> PDF local;
- 19I.18J acredita PDF local -> fuente oficial exacta.

Esto **no** modifica el registro 19I.18E y **no** equivale a autorización
jurídica final.

UNAM y PRODECON continúan fuera de este gate y requieren revisión separada.

## Implementación

```powershell
pytest tests/test_runtime_normative_legal_basis_19i18j4.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest

python -m scripts.audit_runtime_normative_legal_basis_19i18j4
```

Resultado esperado con el estado actual:

- `rmf_2026`: base jurídica candidata soportada, pero redistribución pendiente;
- los 13 documentos de Cámara: procedencia oficial exacta pendiente;
- UNAM y PRODECON: revisión separada;
- `automatic_promotion_performed=False`;
- `public_release_allowed=False`.

## Limitaciones

Este sprint no sustituye asesoría jurídica, no infiere permiso por
accesibilidad pública, no asume fines no lucrativos y no autoriza GitHub
Release, Render ni redistribución comercial.
