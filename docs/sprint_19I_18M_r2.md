# Sprint 19I.18M-r2 — sanitización de rutas Windows incrustadas

## Diagnóstico

19M-r1 saneó correctamente las rutas absolutas que constituían el valor
completo de un campo JSON. `manifest.json` quedó limpio.

`chunks.jsonl` todavía contiene al menos una ruta Windows absoluta incrustada
dentro de una cadena mayor. La auditoría estricta la detectó y bloqueó el
bundle, que es el comportamiento correcto.

## Corrección

r2 añade sanitización de rutas Windows incrustadas dentro de valores string.
La sustitución se aplica únicamente a la copia de staging y conserva el nombre
final del archivo.

Ejemplo:

`build source: D:\...\Corpus app\CFF.pdf`

pasa a:

`build source: CFF.pdf`

El runtime 19K original permanece intacto.

## Reintento

El primer intento r1 sí creó el directorio de salida antes de fallar. Por eso
debe eliminarse únicamente:

`dist/public_release_candidate_19i18m`

antes de ejecutar nuevamente el builder.
