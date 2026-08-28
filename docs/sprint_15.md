# Sprint 15 — Seguridad y robustez

## Objetivo

Endurecer la frontera HTTP y la entrada del usuario sin alterar la lógica fiscal,
normativa, de reglas, cálculo, CBR, RAG ni trazabilidad.

## Controles implementados

La aplicación incorpora:

- `TrustedHostMiddleware` con hosts configurables;
- límite global de cuerpo HTTP;
- headers de seguridad;
- `X-Request-ID` generado por el servidor;
- `Cache-Control: no-store` en `/api/*`;
- HSTS únicamente en producción;
- rechazo de origen cruzado en la consulta web;
- rate limiting por IP observada por ASGI;
- rate limiter con memoria acotada;
- errores de validación que no reflejan el valor inválido;
- error 500 controlado sin stack trace al cliente;
- normalización Unicode NFKC;
- rechazo de caracteres de control y fragmentación extrema;
- heurística de señales de prompt injection;
- redacción de secretos comunes en logging;
- `extra="forbid"` para el contrato de consulta;
- documentación OpenAPI deshabilitada en producción por defecto.

## Prompt injection

La defensa se aplica en dos capas.

Primero, la frontera web detecta señales explícitas como intento de anular
instrucciones, solicitar el prompt del sistema o asumir el rol del sistema.

Segundo, los prompts LLM existentes ya separan instrucciones y evidencia:
la consulta y los documentos recuperados se tratan como datos no confiables.

La heurística no es un clasificador probabilístico y puede producir falsos
positivos o falsos negativos. Por eso no sustituye el aislamiento estructural
de roles, la validación de salidas ni los motores deterministas.

## Headers

Para rutas ordinarias se añaden:

`Content-Security-Policy`, `Permissions-Policy`, `Referrer-Policy`,
`X-Content-Type-Options`, `X-Frame-Options` y `X-Request-ID`.

La CSP estricta se omite en `/docs` y `/redoc` durante desarrollo porque la UI
Swagger/Redoc de FastAPI usa recursos externos. En producción la documentación
automática queda deshabilitada.

HSTS se activa únicamente cuando `ENVIRONMENT=production`, evitando contaminar
el desarrollo local por HTTP.

## Rate limiting

El endpoint de consulta limita solicitudes mediante una ventana en memoria.

Valores por defecto:

- 30 consultas;
- ventana de 60 segundos;
- máximo de 10,000 claves en memoria.

Este mecanismo es apropiado para una sola instancia. No es un rate limiter
distribuido. Si el despliegue futuro usa múltiples procesos o instancias, se
debe reemplazar por un backend compartido gratuito compatible con la
arquitectura o por controles equivalentes del proveedor.

No se confía directamente en `X-Forwarded-For` suministrado por el cliente.

## Tamaño de solicitudes

El límite global por defecto es 1 MiB. La consulta textual permanece limitada
a 4,000 caracteres mediante Pydantic. El middleware cuenta bytes aun cuando el
cuerpo llegue en varios frames ASGI.

## Logging

No se registra el texto de la consulta. El filtro adicional intenta ocultar
formas comunes de:

- `Authorization: Bearer`;
- `api_key`;
- `password`;
- `secret`.

La redacción es una defensa adicional, no una licencia para registrar datos
fiscales o secretos.

## Configuración

Variables nuevas:

```text
TRUSTED_HOSTS_CSV=127.0.0.1,localhost,testserver
MAX_REQUEST_BODY_BYTES=1048576
CONSULTATION_RATE_LIMIT=30
CONSULTATION_RATE_WINDOW_SECONDS=60
```

En Render se deberá definir `TRUSTED_HOSTS_CSV` con el hostname real del
servicio antes del despliegue.

## Pruebas

Se verifican normalización, caracteres de control, prompt injection, rate
limiting, límite de claves, CSP, headers, host no confiable, same-origin,
413 por cuerpo excesivo, 422 sin eco de entrada, redacción de secretos y
compatibilidad de `/docs` en desarrollo.

## Deuda técnica revisada

El warning:

`StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`

no bloquea ejecución ni pruebas. No se añade una dependencia nueva solo para
silenciarlo sin validar primero su compatibilidad con FastAPI/Starlette. Se
mantiene registrado como deuda técnica y debe resolverse mediante una
actualización compatible del stack de pruebas, no ocultando el warning.

## Limitaciones

Todavía no hay autenticación, autorización, cifrado de datos de aplicación,
gestión distribuida de rate limiting, WAF, auditoría externa, escaneo SAST/DAST
de CI ni política de retención para datos fiscales reales.

No debe considerarse que estos controles convierten el sistema en apto para
almacenar información fiscal sensible real sin una evaluación de seguridad
adicional.

## Criterios de aceptación

- Ruff sin errores;
- suite completa de pytest sin fallos;
- mypy sin errores;
- página `/` operativa;
- `/health` operativo;
- host no confiable rechazado;
- origen cruzado rechazado;
- cuerpo excesivo devuelve 413;
- entrada inválida no se refleja;
- señal de prompt injection no llega al runner;
- headers de seguridad presentes;
- consulta normal conserva el comportamiento esperado.
