# Sprint 8 — Motor normativo y vigencia temporal

## Objetivo

Determinar de manera determinista si una versión normativa es aplicable a una fecha
y, cuando exista, a un ejercicio fiscal consultado.

## Flujo

`unidad normativa → versiones → fecha/ejercicio consultado → evaluación temporal → selección`

## Decisiones posibles

- `applicable`
- `not_yet_effective`
- `expired`
- `fiscal_year_mismatch`
- `unknown_validity`

La ausencia de límites temporales suficientes no se interpreta como vigencia. El motor
se abstiene y marca revisión humana.

## Diseño

La lógica temporal está implementada mediante funciones puras. La persistencia queda
aislada en `NormativeRepository` y el acceso de aplicación en `NormativeService`.

El motor no depende de Llama. RAG puede recuperar candidatos, pero la aplicabilidad
temporal debe resolverse mediante esta capa determinista.

## Endpoint

```text
GET /normative/legal-units/{legal_unit_id}/applicable
```

Parámetros:

- `query_date=YYYY-MM-DD`
- `fiscal_year=YYYY` opcional

## CLI

```powershell
python -m scripts.check_normative_validity `
  --legal-unit-id 1 `
  --version-label "2026-A" `
  --effective-from 2026-01-01 `
  --effective-to 2026-12-31 `
  --fiscal-year 2026 `
  --query-date 2026-08-27 `
  --query-fiscal-year 2026
```

## Seguridad y robustez

- validación de rangos;
- intervalos coherentes;
- no se asume vigencia por ausencia de datos;
- no se delega vigencia al LLM;
- resultados explicables mediante `decision` y `reason`;
- revisión humana cuando la vigencia no puede demostrarse.

## Limitaciones

Este sprint no resuelve aún derogaciones complejas, disposiciones transitorias,
vigencia parcial por fracción/inciso, conflictos entre cuerpos normativos ni
jurisprudencia. Esos casos requieren reglas adicionales y trazabilidad normativa más rica.
