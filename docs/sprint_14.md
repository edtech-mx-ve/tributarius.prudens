# Sprint 14 — Interfaz web

## Objetivo

Añadir una interfaz web mínima, responsiva y accesible que consuma resultados
estructurados sin duplicar normativa, reglas, cálculos, CBR ni razonamiento LLM.

## Arquitectura

`HTML semántico + CSS móvil primero + JavaScript mínimo → FastAPI`

La ruta pública `/` entrega la interfaz. Los recursos estáticos se sirven bajo
`/static` y el contrato de consulta se expone en `POST /api/v1/consultations`.

La capa web está dividida en:

- schemas de entrada/salida;
- servicio de frontera;
- adaptador de resultado canónico;
- presenter;
- plantilla HTML;
- CSS;
- JavaScript.

## Estado del backend

El endpoint no inventa resultados. Por defecto devuelve `not_configured`
porque el runtime real requiere configurar índices, corpus, reglas, tarifas y
proveedor Llama. La interfaz muestra ese estado de forma explícita.

`CanonicalWebRunner` permite conectar posteriormente un motor que produzca
`CanonicalExecutionResult`. El presenter proyecta ese objeto hacia una vista
reducida sin recalcular ni reinterpretar el resultado.

## Seguridad

- consulta entre 3 y 4,000 caracteres;
- modo limitado a contribuyente, estudiante o profesional;
- ejercicio fiscal validado;
- JSON enviado mediante `fetch`;
- resultados renderizados con `textContent`, no `innerHTML`;
- mensaje explícito para evitar RFC, CURP, contraseñas, cuentas y domicilios;
- excepciones de runtime no se exponen al cliente;
- no hay persistencia automática del contenido del formulario.

## Accesibilidad

La interfaz usa landmarks semánticos, labels explícitos, enlace de salto,
estados con `aria-live`, foco visible, contraste alto, targets táctiles y
estructura móvil primero. La revisión manual WCAG 2.2 AA sigue siendo necesaria
antes del despliegue público.

## Rendimiento

No hay framework JavaScript ni librería CSS. Los assets son locales y pequeños.
No se incluyen fuentes externas, trackers ni imágenes pesadas. Los objetivos de
despliegue siguen siendo LCP <= 2.5 s, INP <= 200 ms y CLS <= 0.1; deben medirse
en el entorno Render real, no inferirse de pruebas unitarias.

## Privacidad

La interfaz recuerda que no deben introducirse identificadores innecesarios.
La aplicación todavía no debe usarse para información fiscal sensible real
hasta completar el Sprint 15 de seguridad y robustez.

## Pruebas

Las pruebas verifican:

- render de la página;
- disponibilidad CSS/JS;
- validación Pydantic;
- ausencia de backend fiscal simulado;
- inyección de un runner;
- presenter de `CanonicalExecutionResult`.

## Limitaciones

La UI no configura todavía el runtime completo de RAG/Llama desde producción.
No existe autenticación, rate limiting, CSP endurecida ni persistencia de
sesiones. Tampoco se ha realizado auditoría manual con lector de pantalla ni
medición Lighthouse/CrUX en hosting real.

## Criterios de aceptación

- `/` responde HTML;
- CSS y JavaScript cargan;
- formulario utilizable con teclado y móvil;
- entrada inválida produce 422;
- backend no configurado se declara, no se simula;
- presenter consume resultado canónico;
- `/health` y `/docs` permanecen operativos;
- Ruff, pytest y mypy sin errores bloqueantes.
