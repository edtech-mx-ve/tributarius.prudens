# Sprint 19I.18S-r16D.0.3 — Canonical E2E alignment

El diagnóstico r16D.0.2 demostró que 02, 03 y 06 usaban consultas distintas de
las aceptadas por el gate r15.3. Eso cambia intención, hechos extraídos y
promoción normativa, por lo que no constituye una comparación de regresión
válida.

Este hotfix alinea E2E-01..06 con las consultas canónicas del gate r15.3 y
mantiene las comprobaciones nuevas de r16:

- Unicode público;
- coherencia de trace normativa para IVA;
- preservación del backend lexical CPU;
- ausencia de cálculo ISR no sustentado;
- detección adversarial;
- mensajes de fallo accionables.

No se modifica el runtime ni el motor jurídico.
