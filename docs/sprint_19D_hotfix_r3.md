# Sprint 19D hotfix r3

Corrige exclusivamente la aserción de la prueba de regresión cross-volume.
`TemporaryDirectory(dir=...)` recibe un `Path` en la implementación productiva;
la prueba anterior comparaba ese `Path` contra un `str`.

La prueba ahora normaliza ambos operandos a `Path.resolve()` y verifica la
ubicación real del staging sin depender del tipo concreto de ruta en Windows.
No modifica código productivo.
