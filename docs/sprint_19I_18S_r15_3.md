# Sprint 19I.18S-r15.3 — Public Runtime E2E Regression Gate

Objetivo: reproducir localmente los seis casos públicos que revelaron defectos de
aplicabilidad y respuesta, usando exclusivamente el candidate r10 reparado y el
backend `lexical_cpu`.

Seguridad:
- SHA-256 r10 fijado y verificado antes de extraer.
- contrato ZIP exacto de cinco archivos;
- extracción en directorio temporal, sin activar ni reemplazar el runtime del repo;
- `stateless_free` + `lexical_cpu`;
- no usa el runtime semántico privado de 16 documentos;
- no hace red ni despliegue.

Aceptación: E2E-01 derechos, E2E-02 obligaciones, E2E-03 ISR incompleto,
E2E-04 IVA temporal, E2E-05 modo inválido y E2E-06 adversarial deben pasar los
gates de aplicabilidad, abstención, revisión humana e integridad de respuesta.
