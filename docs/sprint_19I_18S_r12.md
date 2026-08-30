# Sprint 19I.18S-r12 — CI parity and Unicode integrity

## Objetivo

Cerrar las cinco regresiones detectadas por el `pytest` integral de GitHub Actions
después de r11 sin debilitar los controles fail-closed de integridad.

## Cambios

- Los fixtures históricos de 19M ahora generan `manifest.json`, `chunks.jsonl` e
  `index.faiss` coherentes con el contrato interno exigido por r11.
- Se conserva la verificación estructural SHA/tamaño/conteo/dimensión.
- Se corrige el mojibake UTF-8 del módulo de cold-start 19N.
- Se agregan regresiones que rechazan marcadores de mojibake y comprueban los
  mensajes Unicode usados por las pruebas de tamaño y alineación FAISS.
- No se modifica el candidato público r10 ni su SHA-256.

## Criterios de aceptación

1. Pruebas focalizadas r10-r12 limpias.
2. Ruff limpio.
3. mypy limpio.
4. `pytest` integral sin fallos.
5. `git diff --check` limpio.
6. El ZIP r10 permanece ignorado y conserva SHA-256
   `18ac85d3b2612a3057dd6e24660487457af078eb8abdf2bb94e122c9bc97c514`.
7. No crear tag/release ni modificar Render hasta que el CI del commit r12 esté verde.

## Implementación

Expandir este parche sobre la raíz del repositorio y ejecutar los comandos de
validación indicados por el Tech Lead.
