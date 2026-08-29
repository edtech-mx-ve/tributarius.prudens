# Sprint 19I.18K-r1 — hotfix estático

Corrección mínima previa a la ejecución funcional del runtime público seguro.

Cambios:

- elimina `shutil`, importado pero no utilizado;
- mueve `Iterable` desde `typing` a `collections.abc` para Python 3.12/Ruff.

No modifica:

- composición normativa de 14 documentos;
- exclusión de UNAM/PRODECON;
- SHA canonical esperado;
- filtros;
- pipeline de reconstrucción;
- benchmark ni umbrales;
- gates jurídicos/temporales;
- flags de publicación.

La ejecución funcional de 19I.18K debe realizarse únicamente después de que
pytest específico, Ruff, mypy y pytest completo queden limpios.
