# Sprint 19I.18S-r16A.1 — Encoding repair hotfix

Corrige el supuesto de codificación de r16A. El mojibake observado puede contener
bytes interpretados bajo Windows-1252 además de Latin-1. La reparación ahora
prueba ambas recodificaciones, selecciona sólo una candidata que reduzca
marcadores de daño y conserva intacto Unicode válido.

También normaliza el orden de imports del test y añade regresión para puntuación
Windows-1252.

## Gate

- pytest focalizado;
- Ruff;
- mypy;
- git diff --check.

No modifica rutas, orquestador, Render, runtime r10 ni backend lexical_cpu.
