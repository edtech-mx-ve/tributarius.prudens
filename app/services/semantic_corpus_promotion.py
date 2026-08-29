from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from app.services.legal_boundary_identity_audit import audit_boundary_identity
from app.services.legal_duplicate_boundary_audit import audit_duplicate_boundaries
from app.services.legal_profile_boundary_audit import audit_profile_boundaries
from app.services.semantic_canonical_audit import compare_canonical_corpora
from app.services.semantic_residual_audit import audit_semantic_residuals
from app.services.semantic_source_residual_audit import (
    audit_semantic_source_residuals,
)


class SemanticCorpusPromotionError(RuntimeError):
    """Fallo controlado al promover el candidato semántico."""


@dataclass(frozen=True)
class PromotionGateSummary:
    baseline_chunks: int
    candidate_chunks: int
    candidate_sha256: str
    duplicate_candidate_ids: int
    candidate_empty_text: int
    legitimate_boundaries_total: int
    legitimate_boundaries_missing: int
    duplicate_boundaries_total: int
    duplicate_boundaries_unresolved: int
    semantic_residuals_total: int
    semantic_residuals_safe: int
    semantic_residuals_review: int
    source_residuals_total: int
    source_residuals_safe: int
    source_residuals_review: int
    profile_cases_total: int
    profile_cases_safe: int
    profile_cases_review: int


@dataclass(frozen=True)
class PromotionManifest:
    schema_version: str
    status: str
    baseline_path: str
    candidate_path: str
    promoted_path: str
    baseline_sha256: str
    promoted_sha256: str
    baseline_chunks: int
    promoted_chunks: int
    document_count: int
    canonical_ids: tuple[str, ...]
    gate: PromotionGateSummary


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    ) as handle:
        temporary = Path(handle.name)
        with source.open("rb") as source_handle:
            for block in iter(lambda: source_handle.read(1024 * 1024), b""):
                handle.write(block)
    try:
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _assert_gate(
    gate: PromotionGateSummary,
    *,
    expected_baseline_chunks: int,
    expected_candidate_chunks: int,
) -> None:
    failures: list[str] = []

    if gate.baseline_chunks != expected_baseline_chunks:
        failures.append(
            f"baseline_chunks={gate.baseline_chunks} "
            f"(esperado={expected_baseline_chunks})"
        )
    if gate.candidate_chunks != expected_candidate_chunks:
        failures.append(
            f"candidate_chunks={gate.candidate_chunks} "
            f"(esperado={expected_candidate_chunks})"
        )
    if gate.duplicate_candidate_ids:
        failures.append(
            f"duplicate_candidate_ids={gate.duplicate_candidate_ids}"
        )
    if gate.candidate_empty_text:
        failures.append(f"candidate_empty_text={gate.candidate_empty_text}")
    if gate.legitimate_boundaries_missing:
        failures.append(
            "legitimate_boundaries_missing="
            f"{gate.legitimate_boundaries_missing}"
        )
    if gate.duplicate_boundaries_unresolved:
        failures.append(
            "duplicate_boundaries_unresolved="
            f"{gate.duplicate_boundaries_unresolved}"
        )
    if gate.semantic_residuals_review != 21:
        failures.append(
            "semantic_residuals_review="
            f"{gate.semantic_residuals_review} (esperado=21)"
        )
    if gate.source_residuals_review != 14:
        failures.append(
            f"source_residuals_review={gate.source_residuals_review} "
            "(esperado=14)"
        )
    if gate.profile_cases_review:
        failures.append(f"profile_cases_review={gate.profile_cases_review}")
    if gate.profile_cases_safe != gate.profile_cases_total:
        failures.append(
            f"profile_cases_safe={gate.profile_cases_safe}/"
            f"{gate.profile_cases_total}"
        )

    if failures:
        raise SemanticCorpusPromotionError(
            "Gate de promoción rechazado: " + "; ".join(failures)
        )


def promote_semantic_corpus(
    *,
    baseline_path: Path,
    candidate_path: Path,
    normalized_root: Path,
    catalog_path: Path,
    promoted_path: Path,
    manifest_path: Path,
    expected_baseline_chunks: int = 3174,
    expected_candidate_chunks: int = 2981,
    overwrite: bool = False,
) -> PromotionManifest:
    baseline = baseline_path.expanduser().resolve()
    candidate = candidate_path.expanduser().resolve()
    promoted = promoted_path.expanduser().resolve()
    manifest_output = manifest_path.expanduser().resolve()

    if not baseline.is_file():
        raise SemanticCorpusPromotionError(f"No existe baseline: {baseline}")
    if not candidate.is_file():
        raise SemanticCorpusPromotionError(f"No existe candidato: {candidate}")
    if not overwrite and (promoted.exists() or manifest_output.exists()):
        raise SemanticCorpusPromotionError(
            "Ya existe salida promovida; use --overwrite solo de forma deliberada."
        )

    canonical = compare_canonical_corpora(
        baseline_path=baseline,
        candidate_path=candidate,
    )
    baseline_docs = {item.canonical_id for item in canonical.documents if item.baseline_chunks}
    candidate_docs = {item.canonical_id for item in canonical.documents if item.candidate_chunks}
    if baseline_docs != candidate_docs:
        missing = sorted(baseline_docs - candidate_docs)
        added = sorted(candidate_docs - baseline_docs)
        raise SemanticCorpusPromotionError(
            f"Cobertura documental cambió; missing={missing}; added={added}"
        )

    identity = audit_boundary_identity(
        baseline_path=baseline,
        candidate_path=candidate,
    )
    duplicate = audit_duplicate_boundaries(
        baseline_path=baseline,
        candidate_path=candidate,
    )
    residual = audit_semantic_residuals(
        baseline_path=baseline,
        candidate_path=candidate,
    )
    source_residual = audit_semantic_source_residuals(
        baseline_path=baseline,
        candidate_path=candidate,
        normalized_root=normalized_root,
    )
    profile = audit_profile_boundaries(
        baseline_path=baseline,
        candidate_path=candidate,
        normalized_root=normalized_root,
        catalog_path=catalog_path,
    )

    gate = PromotionGateSummary(
        baseline_chunks=canonical.baseline_chunks,
        candidate_chunks=canonical.candidate_chunks,
        candidate_sha256=canonical.candidate_sha256,
        duplicate_candidate_ids=canonical.duplicate_candidate_ids,
        candidate_empty_text=canonical.candidate_empty_text,
        legitimate_boundaries_total=identity.total_probable_legitimate,
        legitimate_boundaries_missing=identity.missing_boundary_identity,
        duplicate_boundaries_total=duplicate.total_ambiguous,
        duplicate_boundaries_unresolved=duplicate.unresolved,
        semantic_residuals_total=residual.total_residuals,
        semantic_residuals_safe=residual.safe_absorptions,
        semantic_residuals_review=residual.requires_review,
        source_residuals_total=source_residual.total_requires_review,
        source_residuals_safe=source_residual.resolved_safe,
        source_residuals_review=source_residual.still_requires_review,
        profile_cases_total=profile.total_cases,
        profile_cases_safe=profile.resolved_safe,
        profile_cases_review=profile.requires_review,
    )
    _assert_gate(
        gate,
        expected_baseline_chunks=expected_baseline_chunks,
        expected_candidate_chunks=expected_candidate_chunks,
    )

    # Los 21 residuos se cierran por cadena causal:
    # 7 seguros en auditoría fuente↔parser y 14 seguros por perfil real.
    if source_residual.resolved_safe + profile.resolved_safe != residual.requires_review:
        raise SemanticCorpusPromotionError(
            "La cadena de cierre residual no conserva el total esperado: "
            f"{source_residual.resolved_safe}+{profile.resolved_safe}!="
            f"{residual.requires_review}"
        )

    _atomic_copy(candidate, promoted)
    promoted_sha256 = _sha256(promoted)
    if promoted_sha256 != canonical.candidate_sha256:
        raise SemanticCorpusPromotionError(
            "Hash de corpus promovido no coincide con el candidato."
        )

    result = PromotionManifest(
        schema_version="1.0",
        status="approved_semantic_canonical",
        baseline_path=str(baseline),
        candidate_path=str(candidate),
        promoted_path=str(promoted),
        baseline_sha256=canonical.baseline_sha256,
        promoted_sha256=promoted_sha256,
        baseline_chunks=canonical.baseline_chunks,
        promoted_chunks=canonical.candidate_chunks,
        document_count=len(candidate_docs),
        canonical_ids=tuple(sorted(candidate_docs)),
        gate=gate,
    )
    _atomic_json(manifest_output, asdict(result))
    return result
