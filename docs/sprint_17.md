# Sprint 17 — Marco jurisprudencial

## Objetivo

Incorporar una capa jurisprudencial explícitamente separada de la normativa,
activable solo cuando sea pertinente y sin permitir que un criterio
jurisprudencial sustituya por sí mismo la determinación de vigencia normativa,
las reglas ni los cálculos.

El Sprint 17 construye el marco, los contratos, la validación, la recuperación
aislada, la relación con normas, la trazabilidad separada y las métricas
específicas. El razonamiento normativo-jurisprudencial conjunto se reserva para
el Sprint 18.

## Arquitectura

```text
consulta
  ↓
QueryAnalysis
  ↓
Normativa aplicable identificada
  ↓
decisión de activación jurisprudencial
  ├─ no necesaria → continúa sin jurisprudencia
  └─ necesaria
        ↓
registro de metadatos jurisprudenciales
        ↓
retriever aislado source_type=jurisprudencia
        ↓
evaluación de elegibilidad
        ├─ verificación
        ├─ fecha de publicación
        ├─ estado operativo
        ├─ materia
        └─ relación con referencias normativas
        ↓
candidatos jurisprudenciales
        ↓
revisión humana cuando corresponda
```

## Separación normativa / jurisprudencia

`SourceType.NORMATIVA` y `SourceType.JURISPRUDENCIA` siguen siendo capas
distintas.

`JurisprudenceRetriever` fuerza `source_type=jurisprudencia` y comprueba además
que ningún hit devuelto pertenezca a otra capa. Si el retriever subyacente
devuelve normativa, PRODECON o UNAM, la operación falla de forma controlada.

La jurisprudencia no altera en este sprint:

- `applicable_normative_refs`;
- reglas activadas;
- cálculo ISR;
- CBR;
- conclusiones deterministas.

## Modelo jurisprudencial

`app/domain/jurisprudence.py` incorpora un modelo operacional tipado con:

- `document_id`;
- `identifier`;
- `title`;
- `court_or_body`;
- `criterion_type`;
- `publication_date`;
- `status`;
- `matter`;
- `source_reference`;
- `source_sha256`;
- `verified`;
- `related_normative_refs`;
- `relation_type`;
- `notes`.

Las categorías son **operacionales del proyecto**. No se presentan como una
reproducción exacta del esquema de una base oficial ni como una determinación
jurídica automática.

Estados operacionales:

- `current`;
- `historical`;
- `superseded`;
- `invalidated`;
- `unknown`.

Tipos de relación con norma:

- `interprets`;
- `complements`;
- `distinguishes`;
- `conflicts`;
- `cites`;
- `unknown`.

Un estado o una relación no se infieren libremente por Llama. Deben proceder de
metadatos controlados y trazables.

## Activación

`decide_jurisprudence_activation()` activa la capa cuando:

- la jurisprudencia fue solicitada explícitamente;
- existe una consulta interpretativa con norma aplicable;
- existe ambigüedad con norma aplicable;
- se analiza un acto de autoridad;
- se estudian opciones de defensa.

Las consultas ordinarias de obligaciones, derechos, aprendizaje o cálculo no
activan jurisprudencia por defecto.

La ausencia de jurisprudencia no bloquea la operación normativa ordinaria.

## Elegibilidad

`assess_jurisprudential_candidate()` no decide el fondo del conflicto. Evalúa
si un candidato puede presentarse como evidencia jurisprudencial.

Se excluye cuando:

- el metadato no está verificado;
- la publicación es posterior a la fecha de consulta;
- el estado es `superseded` o `invalidated`;
- la materia solicitada no coincide.

Se exige revisión humana para estados históricos/desconocidos, relaciones
`conflicts`/`unknown` y candidatos sin relación con las referencias normativas
actualmente aplicables.

## Metadatos e ingestión

El registro operacional usa JSONL UTF-8 y un máximo de 5 MiB.

```powershell
python -m scripts.validate_jurisprudence_metadata `
  --metadata ".\jurisprudence\fixtures\metadata_synthetic.jsonl"
```

Resultado esperado:

```text
OK: 3 registros jurisprudenciales; verified=3; sin persistir cambios.
```

No se ejecuta código externo, no se usa `eval`/`exec` y los campos adicionales
son rechazados por el esquema.

## Smoke de elegibilidad

```powershell
python -m scripts.assess_jurisprudence_candidates `
  --metadata ".\jurisprudence\fixtures\metadata_synthetic.jsonl" `
  --query-date "2026-08-28" `
  --norm-ref "NORM_TEST_ISR_2026" `
  --matter "fiscal"
```

La fixture contiene tres registros sintéticos:

- uno vigente operacionalmente y relacionado;
- uno histórico;
- uno superado.

El resultado esperado contiene:

```text
candidate_count = 3
eligible_count = 2
```

La fixture es exclusivamente de ingeniería y no representa jurisprudencia
mexicana real.

## Trazabilidad

`EvidenceKind` incorpora `JURISPRUDENCE`.

`TraceabilityRecord` incorpora el campo separado:

```text
jurisprudential_sources
```

Los resultados canónicos previos siguen siendo compatibles porque el campo
tiene valor por defecto vacío. El Sprint 18 poblará este campo desde el
orquestador jurisprudencial.

## Evaluación específica

`jurisprudence/evaluation.py` implementa:

- `activation_accuracy`;
- `relevance_precision`;
- `norm_relation_recall`;
- `spurious_retrieval_rate`.

La métrica de recuperación espuria es explícita porque recuperar criterios
jurisprudenciales cuando no corresponden es un fallo, aunque el texto sea
semánticamente parecido.

Umbrales iniciales del evaluador jurisprudencial:

```text
activation_accuracy       = 1.00
relevance_precision      >= 0.95
norm_relation_recall     >= 0.80
spurious_retrieval_rate  <= 0.05
```

Son criterios de ingeniería iniciales, no certificación jurídica.

## Seguridad

Los documentos recuperados siguen siendo datos no confiables para el LLM.

La capa no permite que texto jurisprudencial:

- modifique instrucciones del sistema;
- ejecute código;
- altere reglas deterministas;
- cambie una referencia normativa aplicable;
- recalcule impuestos;
- se convierta automáticamente en precedente aplicable.

Los conflictos y estados dudosos requieren revisión humana.

## Persistencia

No se añade migración Alembic en Sprint 17. El registro JSONL sirve como
contrato de ingestión/validación y artefacto versionable. La persistencia
relacional jurisprudencial se introducirá solo cuando el modelo de campos
oficiales y el flujo de actualización estén estabilizados.

## Pruebas

La suite incorpora pruebas de:

- activación y no activación;
- interpretación y ambigüedad;
- metadatos inválidos;
- duplicados;
- estados históricos/superados;
- publicación futura;
- metadatos no verificados;
- relación con norma;
- aislamiento del retriever;
- detección de fuente incorrecta;
- límites de `top_k`;
- recuperación espuria;
- trazabilidad separada;
- CLIs de validación y evaluación.

## Limitaciones

- No se ha conectado todavía esta capa al razonamiento híbrido final.
- No se resuelven conflictos entre criterios.
- No se asigna peso por órgano, jerarquía o tipo de criterio.
- No se infiere obligatoriedad jurídica.
- El esquema es operacional y debe mapearse a los campos de las fuentes
  oficiales que se incorporen.
- No hay corpus jurisprudencial real incluido.
- No se realizan conclusiones de defensa basadas automáticamente en criterios.
- La integración normativa-jurisprudencial corresponde al Sprint 18.

## Criterios de aceptación

- Ruff limpio.
- Pytest completo sin fallos.
- Mypy sin errores.
- Metadatos sintéticos validados por CLI.
- Evaluación de candidatos ejecutable.
- Jurisprudencia desactivada en consultas ordinarias.
- Solicitud explícita activa jurisprudencia.
- Candidato superado es excluido.
- Candidato histórico requiere revisión.
- Fuente no jurisprudencial en el retriever es rechazada.
- Trazabilidad dispone de campo jurisprudencial separado.
- Evaluación detecta recuperación jurisprudencial espuria.
