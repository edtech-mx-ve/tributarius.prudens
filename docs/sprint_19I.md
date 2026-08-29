# Sprint 19I — Evidencia, fuentes y trazabilidad en interfaz web

## Objetivo

Mostrar la salida real del runtime 19H sin reinterpretarla en el navegador:
fuentes normativas separadas de doctrina/orientación, jurisprudencia separada,
metadatos documentales, fragmentos recuperados, incertidumbre, revisión humana
y eventos de trazabilidad.

## Implementación

El presenter expone una proyección de lectura del resultado canónico:
- fuente, rol, versión, ejercicio, unidad, páginas y fragmento;
- folio, intención, fecha, ejercicio, eventos y huella canónica;
- no se expone `query_sha256`, para evitar mostrar una huella de una entrada del usuario.

La UI usa HTML semántico, `details/summary`, `aria-live`, diseño móvil primero y
JavaScript modular mínimo. Todo dato recuperado se inserta con `textContent`;
no se usa `innerHTML`.

## Seguridad y robustez

La UI no ejecuta contenido recuperado. Los documentos RAG son datos, no
instrucciones. La clasificación visual no modifica el ranking ni la conclusión.
La jurisprudencia permanece en una sección separada. La revisión humana se
muestra cuando el resultado canónico la exige.

## Criterios de aceptación

1. Fuentes normativas y fuentes de apoyo se muestran por separado.
2. Jurisprudencia solo se muestra si existe.
3. Cada evidencia puede mostrar versión, unidad, páginas, score y fragmento.
4. Se muestran folio y eventos de trazabilidad.
5. No se expone `query_sha256`.
6. No se usa `innerHTML`.
7. Ruff, mypy y pytest completos pasan.
8. Prueba HTTP local confirma que `/`, `/health`, `/ready` y una consulta real responden.
