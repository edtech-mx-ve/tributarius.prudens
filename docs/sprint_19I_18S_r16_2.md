# Sprint 19I.18S-r16A.2 — Lossy mojibake repair

## Causa raíz

Las cadenas observadas (`PolÃtica`, `jurÃdica`, `Ãndice`) no siempre contienen
todos los caracteres del mojibake reversible. En particular, ciertos caracteres
de control/soft-hyphen pueden perderse durante almacenamiento, renderizado o
copiado. Una recodificación CP1252/Latin-1 no puede reconstruir información que
ya no está presente.

## Corrección

Se mantiene primero la reparación reversible CP1252/Latin-1. Para daño truncado
se añade un vocabulario explícito, pequeño y auditable de formas realmente
observadas. No se adivinan secuencias desconocidas.

## Seguridad

Unicode válido permanece intacto. Una secuencia truncada desconocida se conserva
para evitar correcciones semánticas inventadas. No se modifica runtime, RAG,
política temporal ni despliegue.
