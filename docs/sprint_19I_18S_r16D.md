# Sprint 19I.18S-r16D — E2E Regression Gate

## Objetivo

Automatizar localmente E2E-01..06 sobre la API HTTP real después de r16C.1.

## Cobertura

- derechos;
- obligaciones;
- ISR incompleto;
- IVA fail-closed;
- validación de modo inválido (422);
- consulta adversarial;
- ausencia de mojibake público conocido;
- coherencia del evento `normative` en IVA;
- conservación de `fiscal_year=2026`;
- backend `legal_hybrid_lexical_cpu_19s_r14`;
- cero promoción normativa en casos fail-closed.

## Seguridad

El script sólo realiza peticiones a la URL indicada. No modifica archivos,
índices, reglas, corpus ni base de datos. Por defecto usa localhost.

## Criterio de aceptación

Los seis casos deben imprimir PASS y finalizar con:

`PASS: r16D E2E-01..06 local.`

Un fallo produce código de salida 1, pero no ejecuta `exit` en PowerShell.
