# Sprint 6 — Integración de Llama

## Objetivo

Integrar una capa LLM local, reemplazable y verificable sobre el retriever del Sprint 5,
sin transferir autoridad normativa, de cálculo o decisión al modelo generativo.

## Arquitectura

`consulta → retriever → evidencia → contexto estructurado → Llama → JSON → validador`

La salida generativa solo se acepta cuando:

1. satisface el esquema Pydantic;
2. cita únicamente `chunk_id` recuperados;
3. conserva incertidumbres explícitas;
4. no intenta sustituir las reglas, los cálculos o la vigencia normativa.

Si no se recupera evidencia, la generación se omite y el sistema se abstiene.

## Proveedores

- `MockLLMProvider`: determinista y offline para tests.
- `LlamaCppProvider`: local CPU, GGUF, mediante `llama-cpp-python`.

No se integra ninguna API comercial ni se requieren claves.

## Seguridad

El prompt de sistema declara los documentos recuperados como datos no confiables. Las
instrucciones embebidas dentro del corpus no tienen autoridad sobre el sistema. El
contexto se limita en tamaño y la salida se valida antes de utilizarse.

## Reproducibilidad

El proveedor llama.cpp usa:

- CPU (`n_gpu_layers=0`);
- `temperature=0.0`;
- semilla configurable, por defecto `42`;
- salida JSON Schema;
- límite explícito de tokens.

## Uso mock

```powershell
python -m scripts.explain_with_llama `
  --index-dir ".\indexes\normativa" `
  --query "¿Qué obligaciones fiscales están respaldadas por la evidencia?" `
  --top-k 5 `
  --source-type normativa `
  --provider mock `
  --embedding-local-files-only
```

## Uso Llama GGUF local

La instalación estándar no obliga a compilar llama.cpp. Cuando se quiera probar un
modelo GGUF real:

```powershell
pip install -e ".[llama]"
```

Luego:

```powershell
python -m scripts.explain_with_llama `
  --index-dir ".\indexes\normativa" `
  --query "¿Qué obligaciones fiscales están respaldadas por la evidencia?" `
  --top-k 5 `
  --source-type normativa `
  --provider llama-cpp `
  --model-path "D:\modelos\llama-model.gguf" `
  --n-ctx 4096 `
  --max-tokens 700 `
  --seed 42 `
  --embedding-local-files-only
```

## Criterios de aceptación

- Proveedor abstracto y sustituible.
- Mock determinista.
- Llama local GGUF sin API comercial.
- Validación de ruta y formato del modelo.
- CPU explícita.
- JSON estructurado validado por Pydantic.
- Citas restringidas a evidencia recuperada.
- Abstención automática sin evidencia.
- Protección básica contra prompt injection documental.
- Tests offline sin descargar ni cargar un modelo real.
- Ruff, pytest y mypy limpios en el entorno local.

## Limitaciones

- El Sprint no decide qué variante de Llama desplegar; debe medirse contra RAM, CPU,
  latencia, contexto y disponibilidad gratuita antes de fijarla.
- La salida estructurada reduce, pero no elimina, alucinaciones semánticas.
- La aplicabilidad normativa y la jurisprudencia siguen fuera de la autoridad del LLM.
- No se implementa todavía análisis semántico de la consulta; corresponde al Sprint 7.
