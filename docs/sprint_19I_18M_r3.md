# Sprint 19I.18M-r3 — corrección del detector de rutas privadas

## Diagnóstico confirmado

La auditoría r2 seguía marcando `chunks.jsonl`, pero la inspección directa
demostró:

- `Select-String` encontraba líneas jurídicas normales;
- la búsqueda Python específica de `X:\` devolvió 0 coincidencias en staging;
- la misma búsqueda devolvió 0 coincidencias en el runtime fuente.

Por tanto, el problema era un falso positivo del detector, no una ruta privada
residual.

## Corrección

r3 deja de decidir sobre JSON/JSONL mediante búsqueda indiscriminada del texto
serializado. Ahora:

1. parsea JSON/JSONL;
2. inspecciona solamente valores `str`;
3. exige una ruta Windows estructural `X:\segmento\archivo`;
4. mantiene detección de rutas privadas POSIX `/Users/...` y `/home/...`;
5. añade regresiones con texto jurídico que incluye `Artículo`, `fiscal:`,
   incisos y dos puntos;
6. conserva detección positiva de rutas Windows reales;
7. conserva sanitización de rutas reales solo en staging.

## Seguridad

No se relajan:

- identidad documental bloqueada;
- secretos;
- extensiones prohibidas;
- symlinks;
- manifest y hashes;
- bloqueo jurídico/temporal de publicación.

## Reintento

Eliminar únicamente el staging fallido de 19M antes de aplicar r3.
No modificar ni borrar `dist/public_safe_runtime_19i18k`.
