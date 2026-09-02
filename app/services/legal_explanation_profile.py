from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.explanation_mode import ExplanationMode
from app.domain.legal_explanation import (
    LegalExplanationInvariant,
    LegalExplanationProfile,
    MatureLegalExplanationContext,
)

if TYPE_CHECKING:
    from llm.models import DeterministicEvidence


_PROFILES: dict[ExplanationMode, LegalExplanationProfile] = {
    ExplanationMode.TAXPAYER: LegalExplanationProfile(
        mode=ExplanationMode.TAXPAYER,
        audience_label="Contribuyente",
        communication_goal=(
            "Explicar la consecuencia práctica, las acciones relevantes y el "
            "fundamento indispensable sin modificar el razonamiento jurídico."
        ),
        section_order=[
            "respuesta_directa",
            "que_significa_para_ti",
            "que_hacer",
            "fundamento",
            "incertidumbres_y_revision",
        ],
        style_instructions=[
            "Usar lenguaje claro, directo y accesible para el contribuyente.",
            "Explicar primero la consecuencia práctica y después su fundamento.",
            "Evitar tecnicismos innecesarios sin alterar la conclusión jurídica.",
        ],
    ),
    ExplanationMode.STUDENT: LegalExplanationProfile(
        mode=ExplanationMode.STUDENT,
        audience_label="Estudiante",
        communication_goal=(
            "Hacer visible el razonamiento jurídico y la relación entre hechos, "
            "normas, reglas, evidencia y conclusión."
        ),
        section_order=[
            "problema_juridico",
            "hechos_relevantes",
            "fundamento",
            "razonamiento_paso_a_paso",
            "conclusion",
            "incertidumbres_y_revision",
        ],
        style_instructions=[
            "Explicar conceptos jurídicos con lenguaje pedagógico.",
            "Desarrollar el razonamiento paso a paso.",
            "Relacionar hechos, normas y conclusión de forma explícita.",
        ],
    ),
    ExplanationMode.PROFESSIONAL: LegalExplanationProfile(
        mode=ExplanationMode.PROFESSIONAL,
        audience_label="Profesional",
        communication_goal=(
            "Exponer de forma técnica, compacta y trazable el fundamento, "
            "aplicabilidad, excepciones, riesgos y conclusión jurídica."
        ),
        section_order=[
            "cuestion_juridica",
            "hechos_y_supuestos",
            "marco_normativo",
            "analisis",
            "criterios_y_precedentes",
            "conclusion",
            "riesgos_y_revision",
        ],
        style_instructions=[
            "Usar lenguaje jurídico técnico y conciso.",
            "Priorizar fundamento, aplicabilidad, excepciones y riesgos.",
            "Exponer argumentos, contraargumentos y consecuencias prácticas.",
        ],
    ),
}


def get_legal_explanation_profile(
    mode: ExplanationMode,
) -> LegalExplanationProfile:
    """Devuelve una copia del perfil comunicativo sin contenido jurídico."""

    return _PROFILES[mode].model_copy(deep=True)


def _invariant_from_deterministic(
    evidence: DeterministicEvidence,
) -> LegalExplanationInvariant:
    return LegalExplanationInvariant(
        applicable_normative_refs=list(evidence.applicable_normative_refs),
        rule_conclusions=list(evidence.rule_conclusions),
        calculations=list(evidence.calculations),
        similar_cases=list(evidence.similar_cases),
        jurisprudential_criteria=list(evidence.jurisprudential_criteria),
        hybrid_relation=evidence.hybrid_relation,
        hybrid_conclusion=evidence.hybrid_conclusion,
        hybrid_controlling_source=evidence.hybrid_controlling_source,
        hybrid_reasons=list(evidence.hybrid_reasons),
        heuristic_signals=list(evidence.heuristic_signals),
        heuristic_priorities=list(evidence.heuristic_priorities),
        heuristic_requires_review=evidence.heuristic_requires_review,
        requires_human_review=evidence.requires_human_review,
    )


def build_mature_legal_explanation_context(
    evidence: DeterministicEvidence,
    mode: ExplanationMode,
) -> MatureLegalExplanationContext:
    """Construye un perfil comunicativo sin concederle control jurídico."""

    return MatureLegalExplanationContext(
        invariant=_invariant_from_deterministic(evidence.model_copy(deep=True)),
        profile=get_legal_explanation_profile(mode),
    )


def assert_explanation_mode_invariance(
    contexts: list[MatureLegalExplanationContext],
) -> None:
    """Falla si un modo de explicación altera el contenido jurídico."""

    if not contexts:
        raise ValueError("Se requiere al menos un contexto de explicación.")

    baseline = contexts[0].invariant
    if any(context.invariant != baseline for context in contexts[1:]):
        raise ValueError(
            "Los modos de explicación alteraron el contenido jurídico invariante."
        )
