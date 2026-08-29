# Aceptación Sprint 19I.18E

- el runtime real se audita por `document_id`;
- se contabilizan chunks y bytes de texto por fuente;
- ninguna fuente se presume redistribuible;
- una fuente verificada exige evidencia explícita;
- cualquier fuente desconocida o ausente bloquea release público;
- el reporte se escribe bajo `reports/`;
- no se modifica corpus, FAISS, metadatos temporales ni runtime;
- no se publica ningún artefacto remoto.

El resultado esperado inicial es un bloqueo seguro del release público.
