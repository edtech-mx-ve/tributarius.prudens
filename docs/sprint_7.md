# Sprint 7 — Query Analyzer

## Objetivo

Convertir la consulta libre del usuario en una representación estructurada antes de
activar RAG, normativa, reglas, cálculos o CBR.

## Flujo

`consulta → normalización → Llama/Mock → JSON → Pydantic → validación determinista`

El analizador produce:

- intención primaria;
- intenciones secundarias;
- hechos explícitos o inferidos;
- entidades;
- datos faltantes;
- ambigüedades;
- solicitud explícita de jurisprudencia;
- necesidad de aclaración;
- necesidad de revisión humana.

## Principios

El Query Analyzer no responde la consulta y no decide vigencia normativa. Tampoco
calcula impuestos ni crea hechos ausentes. La salida LLM siempre atraviesa Pydantic y
reglas deterministas posteriores.

Para ISR e IVA se exigen, como mínimo estructural, `fiscal_year` y `taxpayer_type`;
si no aparecen, se incorporan como datos faltantes y se solicita aclaración.

Las consultas sobre actos de autoridad u opciones de defensa se marcan para revisión
humana de forma conservadora.

`jurisprudence_requested` se activa automáticamente cuando la intención primaria es
pedir jurisprudencia. La activación jurisprudencial por necesidad interpretativa
seguirá perteneciendo al orquestador/normativa en sprints posteriores.

## Seguridad

La consulta del usuario es tratada como datos no confiables. Una instrucción embebida
en el texto de la consulta no puede modificar el prompt de sistema.

## Prueba offline

```powershell
python -m scripts.analyze_query `
  --query "Quiero calcular ISR" `
  --provider mock
```

## Prueba con Llama GGUF

```powershell
python -m scripts.analyze_query `
  --query "Quiero calcular ISR" `
  --provider llama-cpp `
  --model-path "D:\\modelos\\llama-model.gguf" `
  --n-ctx 4096 `
  --max-tokens 700 `
  --seed 42
```

## Criterios de aceptación

- análisis estructurado validado;
- normalización y límites de entrada;
- hechos explícitos/inferidos diferenciados;
- datos faltantes deterministas para cálculos básicos;
- abstención de funciones normativas o de cálculo;
- revisión humana conservadora para actos de autoridad/defensa;
- jurisprudencia explícita separada;
- Mock offline y Llama GGUF sustituibles;
- tests, Ruff y mypy limpios.

## Limitaciones

El análisis de intención todavía no activa automáticamente los motores del sistema.
Eso corresponde al orquestador híbrido posterior. No se mide aún exactitud de intención
con un corpus fiscal curado; esa evaluación se incorporará cuando exista un dataset
anotado de consultas.
