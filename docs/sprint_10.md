# Sprint 10 — Cálculo determinista de ISR

## Objetivo

Incorporar un núcleo reproducible de cálculo de ISR basado exclusivamente en parámetros
tarifarios explícitos, versionados y vinculados a una referencia normativa validada.

## Principio de autoridad

Llama no calcula ISR y RAG no determina importes. El motor recibe hechos validados,
una tarifa verificada y una referencia normativa coincidente. Si ejercicio, periodo o
referencia no coinciden, el cálculo se rechaza.

## Fórmula base del núcleo

`base = ingreso bruto - ingreso exento - deducciones autorizadas`

`excedente = base - límite inferior`

`impuesto marginal = excedente × tasa / 100`

`impuesto previo = cuota fija + impuesto marginal`

`impuesto final = max(0, impuesto previo - acreditamientos)`

Todos los importes intermedios se calculan con `Decimal` y redondeo explícito
`ROUND_HALF_UP`.

## Importante

`calculators/fixtures/isr_test_tariff.json` contiene datos SINTÉTICOS exclusivamente
para pruebas automatizadas. No representa una tarifa fiscal oficial y no debe utilizarse
para orientación tributaria real.

Las tablas oficiales se incorporarán solo mediante fuente oficial verificada, metadatos
de vigencia y pruebas de regresión.

## Seguridad y reproducibilidad

- sin `float` para importes monetarios;
- sin LLM en el cálculo;
- tarifa JSON validada por Pydantic;
- máximo 1 MB por archivo tarifario;
- tarifa obligatoriamente marcada `verified=true`;
- ejercicio, periodicidad y referencia normativa deben coincidir;
- pasos y fórmula quedan registrados en el resultado;
- no se permite una base gravable negativa.

## Limitaciones

El núcleo no modela todavía todos los regímenes, subsidios, retenciones, pagos
provisionales, estímulos, topes, deducciones particulares ni reglas transitorias.
La extensión debe realizarse por módulos respaldados por normativa oficial versionada.
