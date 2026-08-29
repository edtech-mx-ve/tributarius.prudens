# Sprint 19I.18J.12.4-r1 — corrección estática

Hotfix exclusivamente de calidad estática antes de ejecutar el gate funcional.

Corrige:

- F841: elimina la asignación local `root` no utilizada.
- I001: organiza el import de la función privada usada por la prueba mediante
  alias explícito.

No cambia umbrales, SHA del candidato, rutas de promoción, lógica de
reconstrucción, benchmark, snapshot ni rollback.

El comando funcional J.12.4 no debe ejecutarse hasta que pytest, Ruff, mypy y
la suite completa queden limpios.
