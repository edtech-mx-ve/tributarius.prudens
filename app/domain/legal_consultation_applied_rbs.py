from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.domain.hybrid_reasoning import NormalizedReasoningResult, ReasoningSource
from app.domain.rules import RuleEvaluationResult


class LegalConsultationAppliedRBS(BaseModel):
    """G.5: RBS ya aplicado, preservado sin reejecutar reglas."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    rule_evaluation: RuleEvaluationResult
    normalized_reasoning: NormalizedReasoningResult
    hybrid_controlling_source: Literal["rbs"] | None = None

    determinative_role_preserved: Literal[True] = True
    source_results_already_computed: Literal[True] = True
    source_result_reexecuted: Literal[False] = False
    can_create_second_legal_conclusion: Literal[False] = False

    @model_validator(mode="after")
    def validate_applied_rbs(self) -> LegalConsultationAppliedRBS:
        normalized = self.normalized_reasoning
        evaluation = self.rule_evaluation

        if normalized.reasoning_source is not ReasoningSource.RBS:
            raise ValueError("G.5 exige razonamiento normalizado de origen RBS.")

        matched = evaluation.matched_rules

        expected_conclusion = (
            "\n".join(item.conclusion for item in matched)
            if matched
            else None
        )
        if normalized.conclusion != expected_conclusion:
            raise ValueError(
                "G.5 detecto una conclusion RBS distinta de las reglas aplicadas."
            )

        expected_legal_basis = list(
            dict.fromkeys(
                ref
                for item in matched
                for ref in item.normative_refs
                if ref
            )
        )
        if normalized.legal_basis != expected_legal_basis:
            raise ValueError(
                "G.5 detecto una base normativa RBS inconsistente."
            )

        expected_references = list(
            dict.fromkeys(
                [
                    *expected_legal_basis,
                    *[
                        ref
                        for item in matched
                        for ref in item.source_refs
                        if ref
                    ],
                ]
            )
        )
        if normalized.references != expected_references:
            raise ValueError(
                "G.5 detecto referencias RBS inconsistentes."
            )

        if normalized.applicability != bool(matched):
            raise ValueError(
                "G.5 detecto aplicabilidad RBS inconsistente."
            )

        if (
            normalized.requires_review
            != evaluation.requires_human_review
        ):
            raise ValueError(
                "G.5 detecto revision humana RBS inconsistente."
            )

        expected_trace = [
            (
                f"{item.sequence}:{item.rule_id}@"
                f"{item.version}:{item.conclusion_code}"
            )
            for item in evaluation.derivations
        ]
        if not expected_trace:
            expected_trace = [
                f"{item.rule_id}@{item.version}:{item.conclusion_code}"
                for item in matched
            ]

        if normalized.trace != expected_trace:
            raise ValueError(
                "G.5 detecto una traza RBS inconsistente."
            )

        return self
