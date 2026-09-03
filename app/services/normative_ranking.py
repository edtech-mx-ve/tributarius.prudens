from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.domain.query import (
    CBROrientationIntegration,
    MultidimensionalQueryAnalysis,
    NormativeRankingEvidence,
    NormativeRankingEvidenceKind,
    NormativeRankingIntegration,
    NormativeRankingSource,
    NormativeRankingTier,
    PrimarySourceActivation,
    QueryDimensionName,
    RBSOrientationIntegration,
)
from app.services.primary_legal_knowledge import load_primary_knowledge_manifest


class NormativeRankingError(RuntimeError):
    """Error controlado del ranking normativo heurístico D.5."""


class _NormativeRankingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    component_weights: dict[str, float]
    focus_top_k: int = Field(ge=1, le=12)
    minimum_focus_score: float = Field(ge=0, le=1)
    tax_source_map: dict[str, list[str]]
    tax_specific_source_ids: list[str]
    explicit_tax_mismatch_multiplier: float = Field(gt=0, le=1)
    full_normative_corpus_preserved: bool = True
    source_exclusion_enabled: bool = False
    ranking_is_relevance_not_validity: bool = True
    legal_hierarchy_interpreted: bool = False
    requires_normative_validation: bool = True
    requires_temporal_validation: bool = True
    rag_retrieval_enabled: bool = False
    can_control_legal_decision: bool = False

    @model_validator(mode="after")
    def enforce_d5_policy_boundary(self) -> _NormativeRankingPolicy:
        expected = {"primary_activation", "rbs_orientation", "cbr_orientation"}
        if set(self.component_weights) != expected:
            raise ValueError("D.5 requiere exactamente tres componentes de ranking.")
        if any(weight < 0 or weight > 1 for weight in self.component_weights.values()):
            raise ValueError("Los pesos D.5 deben estar entre 0 y 1.")
        if abs(sum(self.component_weights.values()) - 1.0) > 1e-9:
            raise ValueError("Los pesos D.5 deben sumar exactamente 1.0.")
        if len(self.tax_specific_source_ids) != len(set(self.tax_specific_source_ids)):
            raise ValueError("D.5 no admite fuentes fiscales específicas duplicadas.")
        if set(source for values in self.tax_source_map.values() for source in values) - set(
            self.tax_specific_source_ids
        ):
            raise ValueError("D.5 contiene un mapa tributario fuera del conjunto específico.")
        if not self.full_normative_corpus_preserved or self.source_exclusion_enabled:
            raise ValueError("D.5 prioriza; nunca excluye corpus normativos.")
        if not self.ranking_is_relevance_not_validity or self.legal_hierarchy_interpreted:
            raise ValueError("D.5 sólo puede ordenar relevancia heurística.")
        if not self.requires_normative_validation or not self.requires_temporal_validation:
            raise ValueError("D.5 no reemplaza validación normativa ni temporal.")
        if self.rag_retrieval_enabled or self.can_control_legal_decision:
            raise ValueError("D.5 no puede adelantar D.7 ni controlar Legal Decision.")
        return self


class _FiscalCorpusCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    canonical_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=3, max_length=300)
    layer: str = Field(min_length=1, max_length=50)


def _resource_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources"


@lru_cache(maxsize=1)
def load_default_normative_ranking_policy() -> _NormativeRankingPolicy:
    path = _resource_dir() / "normative_ranking_policy.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _NormativeRankingPolicy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise NormativeRankingError("La política de ranking normativo D.5 no es válida.") from exc


@lru_cache(maxsize=1)
def load_default_normative_corpus_catalog() -> dict[str, _FiscalCorpusCatalogEntry]:
    path = _resource_dir() / "fiscal_corpus_15_catalog.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = [_FiscalCorpusCatalogEntry.model_validate(item) for item in payload]
    except (OSError, json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise NormativeRankingError("El catálogo fiscal interno no es válido para D.5.") from exc
    by_id = {item.canonical_id: item for item in entries}
    if len(by_id) != len(entries):
        raise NormativeRankingError("El catálogo fiscal contiene canonical_id duplicados.")
    return by_id


@lru_cache(maxsize=1)
def load_default_normative_corpus_ids() -> tuple[str, ...]:
    manifest = load_primary_knowledge_manifest(
        _resource_dir() / "primary_legal_knowledge_manifest.json"
    )
    return tuple(manifest.normative_corpus_ids)


def _first_dimension(
    multidimensional: MultidimensionalQueryAnalysis,
    name: QueryDimensionName,
) -> str | None:
    return next(
        (item.value for item in multidimensional.dimensions if item.dimension is name),
        None,
    )


def _explicit_tax_compatibility(
    source_id: str,
    query_tax: str | None,
    policy: _NormativeRankingPolicy,
) -> float:
    if query_tax is None or source_id not in policy.tax_specific_source_ids:
        return 1.0
    preferred = set(policy.tax_source_map.get(query_tax, []))
    if source_id in preferred:
        return 1.0
    return policy.explicit_tax_mismatch_multiplier


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _source_from_ref(ref: str) -> str:
    return ref.split(":", 1)[0]


def _primary_component(
    source_id: str,
    activation: PrimarySourceActivation,
) -> tuple[float, list[NormativeRankingEvidence]]:
    evidence: list[NormativeRankingEvidence] = []
    scores: list[float] = []
    for entry in activation.entries:
        if source_id not in entry.candidate_normative_sources:
            continue
        scores.append(entry.score)
        evidence.append(
            NormativeRankingEvidence(
                kind=NormativeRankingEvidenceKind.PRIMARY_SOURCE,
                ref=entry.entry_id,
                upstream_score=entry.score,
                detail=(
                    f"{entry.entry_id} ({entry.manual.value}) orienta hacia {source_id}."
                ),
            )
        )
    return (max(scores) if scores else 0.0), evidence


def _rbs_component(
    source_id: str,
    orientation: RBSOrientationIntegration,
) -> tuple[float, list[NormativeRankingEvidence], list[str], bool]:
    evidence: list[NormativeRankingEvidence] = []
    scores: list[float] = []
    refs: list[str] = []
    blocked = False
    for relation in orientation.relations:
        if source_id not in relation.normative_source_ids:
            continue
        scores.append(relation.score)
        source_refs = [
            ref for ref in relation.exact_normative_refs if _source_from_ref(ref) == source_id
        ]
        refs.extend(source_refs)
        if source_id in relation.blocked_normative_sources:
            blocked = True
        evidence.append(
            NormativeRankingEvidence(
                kind=NormativeRankingEvidenceKind.RBS_ORIENTATION,
                ref=relation.relation_id,
                upstream_score=relation.score,
                detail=f"{relation.relation_id} orienta estructuralmente hacia {source_id}.",
            )
        )
    return (max(scores) if scores else 0.0), evidence, _unique(refs), blocked


def _cbr_component(
    source_id: str,
    orientation: CBROrientationIntegration,
) -> tuple[float, list[NormativeRankingEvidence], list[str]]:
    evidence: list[NormativeRankingEvidence] = []
    scores: list[float] = []
    refs: list[str] = []
    for match in orientation.matches:
        source_refs = [
            ref for ref in match.validated_normative_refs if _source_from_ref(ref) == source_id
        ]
        if not source_refs:
            continue
        if not match.corpus_validated:
            raise NormativeRankingError(
                f"D.5 recibió refs CBR no validadas en {match.situation_id}."
            )
        scores.append(match.similarity)
        refs.extend(source_refs)
        evidence.append(
            NormativeRankingEvidence(
                kind=NormativeRankingEvidenceKind.CBR_ORIENTATION,
                ref=match.situation_id,
                upstream_score=match.similarity,
                detail=(
                    f"{match.situation_id} aporta referencia validada C.7 para {source_id}."
                ),
            )
        )
    return (max(scores) if scores else 0.0), evidence, _unique(refs)


def _validate_upstream(
    corpus_ids: tuple[str, ...],
    activation: PrimarySourceActivation,
    rbs_orientation: RBSOrientationIntegration,
    cbr_orientation: CBROrientationIntegration,
) -> None:
    expected = list(corpus_ids)
    if len(expected) != 12 or len(set(expected)) != 12:
        raise NormativeRankingError("D.5 exige exactamente los 12 corpus normativos A.8.")
    if activation.normative_corpus_ids != expected:
        raise NormativeRankingError("D.2 no conserva el orden canónico A.8 para D.5.")
    if rbs_orientation.normative_corpus_ids != expected:
        raise NormativeRankingError("D.3 no conserva el espacio normativo A.8 para D.5.")
    if cbr_orientation.normative_corpus_ids != expected:
        raise NormativeRankingError("D.4 no conserva el espacio normativo A.8 para D.5.")
    if not all(
        (
            activation.full_normative_corpus_preserved,
            rbs_orientation.full_normative_corpus_preserved,
            cbr_orientation.full_normative_corpus_preserved,
        )
    ):
        raise NormativeRankingError("Una etapa previa intentó reducir el corpus normativo.")
    if not all(
        (
            activation.requires_normative_validation,
            rbs_orientation.requires_normative_validation,
            cbr_orientation.requires_normative_validation,
        )
    ):
        raise NormativeRankingError("D.5 recibió una etapa previa sin frontera normativa.")


def rank_normative_sources(
    multidimensional: MultidimensionalQueryAnalysis,
    primary_activation: PrimarySourceActivation,
    rbs_orientation: RBSOrientationIntegration,
    cbr_orientation: CBROrientationIntegration,
    *,
    policy: _NormativeRankingPolicy | None = None,
    corpus_catalog: dict[str, _FiscalCorpusCatalogEntry] | None = None,
    corpus_ids: tuple[str, ...] | None = None,
) -> NormativeRankingIntegration:
    """Ordena por relevancia los 12 corpus sin excluirlos ni afirmar vigencia."""
    resolved_policy = policy or load_default_normative_ranking_policy()
    resolved_catalog = corpus_catalog or load_default_normative_corpus_catalog()
    resolved_ids = corpus_ids or load_default_normative_corpus_ids()
    _validate_upstream(
        resolved_ids,
        primary_activation,
        rbs_orientation,
        cbr_orientation,
    )

    missing_catalog = [source_id for source_id in resolved_ids if source_id not in resolved_catalog]
    if missing_catalog:
        raise NormativeRankingError(
            f"D.5 no encontró corpus A.8 en el catálogo interno: {missing_catalog}."
        )

    weights = resolved_policy.component_weights
    query_tax = _first_dimension(multidimensional, QueryDimensionName.TAX)
    scored: list[NormativeRankingSource] = []
    for canonical_index, source_id in enumerate(resolved_ids):
        primary_score, primary_evidence = _primary_component(source_id, primary_activation)
        rbs_score, rbs_evidence, rbs_refs, rbs_blocked = _rbs_component(
            source_id, rbs_orientation
        )
        cbr_score, cbr_evidence, cbr_refs = _cbr_component(source_id, cbr_orientation)
        compatibility = _explicit_tax_compatibility(
            source_id, query_tax, resolved_policy
        )
        score = (
            primary_score * weights["primary_activation"]
            + rbs_score * weights["rbs_orientation"]
            + cbr_score * weights["cbr_orientation"]
        ) * compatibility
        catalog_entry = resolved_catalog[source_id]
        if catalog_entry.layer != "normativa":
            raise NormativeRankingError(f"D.5 sólo puede ordenar fuentes normativas: {source_id}.")
        scored.append(
            NormativeRankingSource(
                rank=1,
                corpus_id=source_id,
                title=catalog_entry.title,
                relevance_score=round(score, 6),
                primary_activation_component=round(primary_score, 6),
                rbs_orientation_component=round(rbs_score, 6),
                cbr_orientation_component=round(cbr_score, 6),
                explicit_tax_compatibility=compatibility,
                evidence=[*primary_evidence, *rbs_evidence, *cbr_evidence],
                exact_normative_refs=_unique([*rbs_refs, *cbr_refs]),
                rbs_temporal_block_detected=rbs_blocked,
                focus_selected=False,
                tier=NormativeRankingTier.EXPANSION,
                canonical_order=canonical_index + 1,
                requires_normative_validation=True,
                requires_temporal_validation=True,
                can_control_legal_decision=False,
            )
        )

    scored.sort(key=lambda item: (-item.relevance_score, item.canonical_order))
    focus_ids: list[str] = []
    for index, item in enumerate(scored, start=1):
        item.rank = index
        if (
            len(focus_ids) < resolved_policy.focus_top_k
            and item.relevance_score >= resolved_policy.minimum_focus_score
        ):
            item.focus_selected = True
            item.tier = NormativeRankingTier.FOCAL
            focus_ids.append(item.corpus_id)
        elif item.relevance_score > 0:
            item.tier = NormativeRankingTier.SECONDARY

    exact_refs = _unique([ref for item in scored for ref in item.exact_normative_refs])
    ranking_applied = any(item.relevance_score > 0 for item in scored)
    return NormativeRankingIntegration(
        schema_version=resolved_policy.schema_version,
        ranking_applied=ranking_applied,
        query_tax=query_tax,
        ranked_sources=scored,
        focus_source_ids=focus_ids,
        exact_normative_refs=exact_refs,
        component_weights=dict(weights),
        normative_corpus_ids=list(resolved_ids),
        full_normative_corpus_preserved=True,
        source_exclusion_enabled=False,
        ranking_is_relevance_not_validity=True,
        legal_hierarchy_interpreted=False,
        requires_normative_validation=True,
        requires_temporal_validation=True,
        normative_validation_completed=False,
        temporal_validation_completed=False,
        structural_navigation_enabled=False,
        rag_retrieval_enabled=False,
        can_control_legal_decision=False,
    )
