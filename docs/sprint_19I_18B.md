# Sprint 19I.18B — bootstrap verificable del runtime

Este incremento implementa el instalador que podrá usarse durante el build de
Render una vez que el bundle 19I.18A tenga una URL pública estable.

## Seguridad

- solo HTTPS para fuentes remotas;
- SHA-256 obligatorio;
- límite de descarga de 100 MB por defecto;
- timeout configurable;
- lista cerrada de archivos permitidos;
- rechazo de path traversal / Zip Slip;
- validación de hashes y tamaños internos;
- extracción a staging;
- activación del runtime solo después de todas las validaciones.

La URL pública **no se fija aún**. Primero debe existir el artefacto remoto y
su hash debe coincidir con el bundle local aprobado.

## Prueba local con el bundle 19I.18A

Use un directorio temporal para no reemplazar su runtime actual:

```powershell
$Bundle = "dist\runtime_release_19i18\tributarius-prudens-runtime-semantic-v2.zip"
$Sha = "687c9f6bba0b166b3728ce387d560644523d260cde1f7a298655954e490cbda4"
$Tmp = Join-Path $env:TEMP "tributarius-runtime-bootstrap-test"
Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $Tmp | Out-Null

python -m scripts.install_runtime_release_19i18b `
  --source $Bundle `
  --sha256 $Sha `
  --project-root $Tmp
```

Después de esta prueba deben existir cuatro archivos operativos bajo `$Tmp`.

No modificar todavía `render.yaml`, no hacer push y no crear el release remoto.
