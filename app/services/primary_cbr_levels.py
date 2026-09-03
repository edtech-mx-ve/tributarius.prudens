from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.cbr import CBRCase
from app.domain.primary_cbr_corpus_validation import (
    PrimaryCBRCorpusValidationOutcome,
    PrimaryCBRCorpusValidationReport,
    PrimaryCBRSituationCorpusValidation,
)
from app.domain.primary_cbr_legal_similarity import PrimaryCBRLegalSimilarityIndex
from app.domain.primary_cbr_levels import (
    PrimaryCBRKnowledgeLevel,
    PrimaryCBRLevelAssessment,
    PrimaryCBRLevelRegistry,
    PrimaryCBROperationalBlocker,
)
from app.domain.primary_cbr_normative_citations import PrimaryCBRNormativeCitationLinkage
from app.domain.primary_cbr_problem_institution import PrimaryCBRClassifiedSimilaritySeed


class PrimaryCBRLevelRegistryError(RuntimeError):
    """Error controlado de niveles CBR C.10."""


REQUIRED_OPERATIONAL_CASE_FIELDS: tuple[str, ...] = (
    "taxpayer_type",
    "activity",
    "tax",
    "problem_type",
    "fiscal_year",
)


def load_primary_cbr_level_registry(path: Path) -> PrimaryCBRLevelRegistry:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryCBRLevelRegistryError(f"No existe el registro CBR C.10: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryCBRLevelRegistry.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryCBRLevelRegistryError(
            "El registro de niveles CBR C.10 no es válido."
        ) from exc


def _missing_required_fields(seed: PrimaryCBRClassifiedSimilaritySeed) -> list[str]:
    missing: list[str] = []
    for field_name in REQUIRED_OPERATIONAL_CASE_FIELDS:
        value = getattr(seed, field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field_name)
    return missing


def _consistent_normative_refs(
    validation: PrimaryCBRSituationCorpusValidation,
) -> list[str]:
    refs: list[str] = []
    for article in validation.article_validations:
        if article.validation_outcome is PrimaryCBRCorpusValidationOutcome.CONSISTENT:
            if article.candidate_normative_ref not in refs:
                refs.append(article.candidate_normative_ref)
    return refs


def _blockers(
    *,
    corpus_validated: bool,
    missing_fields: list[str],
    temporal_validation_pending: bool,
) -> list[PrimaryCBROperationalBlocker]:
    blockers: list[PrimaryCBROperationalBlocker] = []
    if not corpus_validated:
        blockers.append(PrimaryCBROperationalBlocker.CORPUS_NOT_VALIDATED)
    if missing_fields:
        blockers.append(PrimaryCBROperationalBlocker.REQUIRED_CASE_FIELDS_MISSING)
    if temporal_validation_pending:
        blockers.append(PrimaryCBROperationalBlocker.TEMPORAL_VALIDATION_PENDING)
    blockers.extend(
        [
            PrimaryCBROperationalBlocker.RESOLUTION_OUTCOME_NOT_VERIFIED,
            PrimaryCBROperationalBlocker.ANONYMIZATION_REVIEW_PENDING,
        ]
    )
    return blockers


def build_primary_cbr_level_registry(
    citation_linkage: PrimaryCBRNormativeCitationLinkage,
    corpus_validation: PrimaryCBRCorpusValidationReport,
    legal_similarity: PrimaryCBRLegalSimilarityIndex,
) -> PrimaryCBRLevelRegistry:
    baselines = {
        citation_linkage.baseline_commit,
        corpus_validation.baseline_commit,
        legal_similarity.baseline_commit,
    }
    if len(baselines) != 1:
        raise PrimaryCBRLevelRegistryError("C.10 debe conservar el baseline C.6/C.7/C.9.")

    c6_by_id = {item.situation_id: item for item in citation_linkage.situations}
    c7_by_id = {item.situation_id: item for item in corpus_validation.situations}
    if set(c6_by_id) != set(c7_by_id):
        raise PrimaryCBRLevelRegistryError("C.10 requiere las mismas situaciones C.6/C.7.")
    profile_ids = [profile.situation_id for profile in legal_similarity.profiles]
    if set(profile_ids) != set(c7_by_id):
        raise PrimaryCBRLevelRegistryError("C.10 requiere exactamente los perfiles C.9.")

    required_fields = list(REQUIRED_OPERATIONAL_CASE_FIELDS)
    missing_model_fields = set(required_fields) - set(CBRCase.model_fields)
    if missing_model_fields:
        raise PrimaryCBRLevelRegistryError(
            "El contrato CBRCase existente perdió campos requeridos por C.10: "
            + ", ".join(sorted(missing_model_fields))
        )

    assessments: list[PrimaryCBRLevelAssessment] = []
    operational_shape_complete_count = 0
    validated_shape_complete_count = 0

    for profile in legal_similarity.profiles:
        c6 = c6_by_id[profile.situation_id]
        c7 = c7_by_id[profile.situation_id]
        if (
            profile.source != c6.source
            or profile.source != c7.source
            or profile.source_entry_id != c6.source_entry_id
            or profile.source_entry_id != c7.source_entry_id
        ):
            raise PrimaryCBRLevelRegistryError(
                f"C.10 perdió identidad fuente en {profile.situation_id}."
            )
        if (
            profile.corpus_validation_outcome != c7.validation_outcome
            or profile.corpus_validated != c7.corpus_validated
            or profile.temporal_validation_pending != c7.temporal_validation_pending
        ):
            raise PrimaryCBRLevelRegistryError(
                f"C.10 debe preservar el estado C.7 en {profile.situation_id}."
            )

        missing_fields = _missing_required_fields(profile.similarity_seed)
        if not missing_fields:
            operational_shape_complete_count += 1
            if c7.corpus_validated:
                validated_shape_complete_count += 1

        validated_level_eligible = (
            c7.corpus_validated
            and c7.validation_outcome is PrimaryCBRCorpusValidationOutcome.CONSISTENT
        )
        blockers = _blockers(
            corpus_validated=validated_level_eligible,
            missing_fields=missing_fields,
            temporal_validation_pending=c7.temporal_validation_pending,
        )
        operational_level_eligible = not blockers
        highest = (
            PrimaryCBRKnowledgeLevel.OPERATIONAL
            if operational_level_eligible
            else PrimaryCBRKnowledgeLevel.VALIDATED
            if validated_level_eligible
            else PrimaryCBRKnowledgeLevel.PRIMARY
        )
        assessments.append(
            PrimaryCBRLevelAssessment(
                situation_id=profile.situation_id,
                source=profile.source,
                source_entry_id=profile.source_entry_id,
                historical_regime_context=profile.historical_regime_context,
                highest_level=highest,
                validated_level_eligible=validated_level_eligible,
                operational_level_eligible=operational_level_eligible,
                corpus_validation_outcome=c7.validation_outcome,
                corpus_validated=c7.corpus_validated,
                validated_normative_refs=_consistent_normative_refs(c7),
                required_case_fields=required_fields,
                unresolved_required_case_fields=missing_fields,
                temporal_validation_pending=c7.temporal_validation_pending,
                resolution_outcome_verified=False,
                anonymization_review_completed=False,
                legal_similarity_enabled=profile.legal_similarity_enabled,
                operational_blockers=blockers,
            )
        )

    highest_level_counts = {level.value: 0 for level in PrimaryCBRKnowledgeLevel}
    blocker_counts = {blocker.value: 0 for blocker in PrimaryCBROperationalBlocker}
    for assessment in assessments:
        highest_level_counts[assessment.highest_level.value] += 1
        for blocker in assessment.operational_blockers:
            blocker_counts[blocker.value] += 1

    return PrimaryCBRLevelRegistry(
        schema_version="1.0",
        baseline_commit=legal_similarity.baseline_commit,
        purpose=(
            "Formalizar C.10 como una promoción fail-closed primary -> validated -> operational. "
            "Las 37 situaciones permanecen conocimiento primario; sólo las compatibles con C.7 "
            "alcanzan validado y ninguna se materializa como CBRCase operativo mientras sigan "
            "pendientes la vigencia por caso, el resultado/resolución y la revisión de "
            "anonimización."
        ),
        source_situation_count=len(assessments),
        primary_membership_count=len(assessments),
        validated_membership_count=sum(
            item.validated_level_eligible for item in assessments
        ),
        operational_membership_count=sum(
            item.operational_level_eligible for item in assessments
        ),
        highest_level_counts=highest_level_counts,
        operational_shape_complete_count=operational_shape_complete_count,
        validated_shape_complete_count=validated_shape_complete_count,
        operational_blocker_counts=blocker_counts,
        assessments=assessments,
        operational_cases=[],
    )


def validate_primary_cbr_level_registry(
    registry: PrimaryCBRLevelRegistry,
    citation_linkage: PrimaryCBRNormativeCitationLinkage,
    corpus_validation: PrimaryCBRCorpusValidationReport,
    legal_similarity: PrimaryCBRLegalSimilarityIndex,
) -> None:
    rebuilt = build_primary_cbr_level_registry(
        citation_linkage,
        corpus_validation,
        legal_similarity,
    )
    if registry != rebuilt:
        raise PrimaryCBRLevelRegistryError(
            "El registro C.10 no es reproducible desde C.6/C.7/C.9."
        )
    if any(
        match.operational_reuse_allowed
        for group in legal_similarity.neighbors
        for match in group.matches
    ):
        raise PrimaryCBRLevelRegistryError(
            "C.10 no puede promover vecinos que C.9 mantiene sin reutilización operativa."
        )
