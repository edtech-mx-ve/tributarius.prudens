# Sprint 19D hotfix r1

Corrige `WinError 17` en Windows cuando `%TEMP%` está en una unidad distinta
al repositorio. El staging temporal del índice se crea ahora dentro del
directorio de destino, manteniendo `os.replace()` en el mismo filesystem y
preservando la publicación atómica de los artefactos.

Incluye una prueba de regresión que verifica que el directorio temporal recibe
como `dir` el directorio de artefactos de runtime.
