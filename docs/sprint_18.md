# Sprint 18 — Razonamiento normativo-jurisprudencial

## Objetivo

Integrar el marco jurisprudencial del Sprint 17 al orquestador híbrido sin
confundir jurisprudencia con normativa ni permitir que un criterio recuperado
altere por sí solo vigencia normativa, reglas o cálculos.

## Flujo

```text
QueryAnalysis
  -> RAG principal (PRODECON / UNAM / NORMATIVA)
  -> aplicabilidad normativa
  -> decisión de activación jurisprudencial
      -> no: stage jurisprudence = skipped
      -> sí:
          -> retriever jurisprudencial separado
          -> elegibilidad / relación con norma
          -> review si corresponde
  -> reglas
  -> cálculo
  -> CBR
  -> contexto determinista estructurado
  -> Llama explica
  -> trazabilidad canónica
```

La recuperación principal excluye `SourceType.JURISPRUDENCIA` incluso cuando
la consulta la solicita. Solo `JurisprudenceRetriever` puede aportar criterios
jurisprudenciales.

## Integración

`HybridOrchestrator` acepta opcionalmente `jurisprudence_retriever`.

La capa jurisprudencial se ejecuta después de determinar
`applicable_normative_refs`, por lo que la relación criterio-norma se evalúa
contra referencias normativas ya validadas.

Si jurisprudencia no es necesaria, el stage queda `skipped`.

Si es necesaria pero el retriever no está configurado, o la recuperación falla,
el stage queda `degraded`, el análisis normativo se conserva y
`requires_human_review=True`.

## Contrato con Llama

`DeterministicEvidence` incorpora `jurisprudential_criteria`.

El contenido transmitido incluye identificador, relación declarada, estado y
referencia de fuente. No se presenta como una instrucción para el modelo ni
como sustituto de la normativa.

Los chunks jurisprudenciales no se mezclan con el `RetrievalResult` principal,
de modo que una cita jurisprudencial no puede hacerse pasar por normativa en
la frontera RAG existente.

## Trazabilidad

Se incorpora `OrchestrationStage.JURISPRUDENCE`.

El resultado canónico incorpora una sección `jurisprudence` solo cuando la
capa fue ejecutada con resultado.

`TraceabilityRecord.jurisprudential_sources` contiene exclusivamente
`EvidenceKind.JURISPRUDENCE`.

Los hashes canónicos anteriores siguen siendo verificables: la clave
`jurisprudence` se incorpora al hash solo cuando existe un resultado
jurisprudencial.

## Reglas de seguridad jurídica

- La jurisprudencia nunca agrega ni elimina `applicable_normative_refs`.
- Un criterio `superseded` o `invalidated` es excluido.
- Un criterio histórico o dudoso propaga revisión humana.
- Una relación `conflicts` no resuelve automáticamente el conflicto.
- Un fallo jurisprudencial no elimina el resultado normativo.
- La ausencia de jurisprudencia no bloquea consultas que no la requieren.
- Llama explica evidencia estructurada; no determina vigencia normativa.
- Las fixtures son sintéticas y no constituyen autoridad jurídica.

## Pruebas

Se cubren:

- orden normativa -> jurisprudencia;
- aislamiento de retrievers;
- activación y degradación;
- preservación normativa ante fallos;
- exclusión de criterio superado;
- propagación de revisión humana;
- trazabilidad jurisprudencial separada;
- integridad canónica;
- compatibilidad con trazas anteriores;
- ausencia de jurisprudencia en el RAG principal.

## Smoke

```powershell
python -m scripts.smoke_normative_jurisprudential
```

Resultado esperado:

```text
OK: norma aplicable=1; jurisprudencia elegible=1; trazabilidad separada=1; integridad=True.
```

## Limitaciones

- No se determina automáticamente obligatoriedad jurídica de un criterio.
- No se implementa jerarquización por órgano o tipo de precedente.
- No se resuelven contradicciones entre múltiples criterios.
- No se incluye corpus jurisprudencial real.
- La calidad jurídica real requiere dataset oficial, metadatos verificados y
  evaluación humana.
- La integración de un modelo Llama real sigue dependiendo de seleccionar un
  modelo compatible con los recursos disponibles.
- No hay migración Alembic en este sprint.

## Criterios de aceptación

- Ruff limpio.
- Pytest completo.
- Mypy estricto sin errores.
- Smoke normativo-jurisprudencial exitoso.
- Normativa y jurisprudencia permanecen separadas.
- Un fallo jurisprudencial degrada sin destruir el resultado normativo.
- La trazabilidad registra fuentes jurisprudenciales en campo independiente.
- La integridad canónica funciona con y sin jurisprudencia.
