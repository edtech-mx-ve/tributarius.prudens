# Sprint 19I.18S-r16D.0.2 — Diagnostic visibility

El primer E2E r16D obtuvo PASS en 01, 04 y 05, pero 02, 03 y 06 fallaron con
mensajes vacíos porque `AssertionError` sin mensaje no expone la condición.

Este incremento no cambia el runtime ni los contratos del gate. Añade un
diagnóstico de sólo lectura para imprimir los campos relevantes de los tres
casos fallidos antes de decidir si existe una regresión real o una expectativa
del gate que no coincide con el contrato r15/r16.

No se debe corregir el motor hasta observar esos valores.
