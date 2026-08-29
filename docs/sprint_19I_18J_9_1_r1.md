# Sprint 19I.18J.9.1 r1 — corrección Ruff

Se corrige únicamente el orden de importación exigido por Ruff:

```python
from dataclasses import asdict, dataclass
```

No cambia lógica, contratos, seguridad ni comportamiento funcional.

Criterios de aceptación:
- prueba focalizada J.9.1;
- Ruff limpio;
- mypy limpio;
- pytest completo limpio salvo warning conocido;
- control real de readiness ejecutable.
