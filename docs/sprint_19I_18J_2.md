# Sprint 19I.18J.2 — verificación oficial desacoplada de red

## Diagnóstico de entrada

La máquina local no puede establecer TCP 443 con
`www.diputados.gob.mx` (`WinError 10060`, `TcpTestSucceeded=False`,
`curl (28) timeout`). Esto confirma que 19I.18J.1 no enfrenta un problema de
Python ni un `hash mismatch`.

## Objetivo

Permitir que la evidencia oficial se adquiera desde otra máquina o red con
conectividad y se transfiera al repositorio para una verificación local,
determinista y fail-closed.

Cadena:

`autoridad HTTPS -> PDF adquirido -> manifest SHA-256 -> transferencia ->`
`auditoría offline -> bridge 19I.18I -> PDF local`

## Política

- una URL no verifica procedencia por sí sola;
- el adquirente solo acepta HTTPS y hosts permitidos;
- se conserva el PDF y un manifest con URL final, hash y tamaño;
- la auditoría offline vuelve a calcular hash y tamaño;
- solo `evidence_sha256 == local_source_sha256` verifica procedencia binaria;
- un PDF oficial vigente con hash distinto se clasifica como
  `official_binary_differs_from_local_pdf`, no como documento inválido;
- no se habilita redistribución;
- `promotion_ready_documents=[]`;
- `public_release_allowed=False`.

## Implementación local

```powershell
pytest tests/test_runtime_official_source_offline_evidence_19i18j2.py -v
ruff check .
mypy app rag llm calculators cbr evaluation jurisprudence scripts
pytest
```

## Adquisición en otra red/máquina

Copie el repositorio o al menos este código a una máquina con acceso a Cámara:

```powershell
python -m scripts.acquire_official_source_evidence_19i18j2 `
  --output-dir dist/official_source_evidence_19i18j2
```

Transfiera **la carpeta completa** `dist/official_source_evidence_19i18j2`
a la misma ruta del repositorio principal.

También puede probar por documento:

```powershell
python -m scripts.acquire_official_source_evidence_19i18j2 `
  --document-id cff `
  --output-dir dist/official_source_evidence_19i18j2
```

## Auditoría offline en la máquina principal

```powershell
python -m scripts.audit_offline_official_source_evidence_19i18j2 `
  --evidence-dir dist/official_source_evidence_19i18j2
```

Finalmente:

```powershell
python -m scripts.audit_runtime_publication_safety_19i18e
$LASTEXITCODE
```

El safety gate debe seguir devolviendo 3.


## Hotfix r1

Corrige únicamente Ruff: elimina `shutil` no usado, ordena imports locales y divide una firma de prueba mayor a 100 caracteres. Sin cambios funcionales.
