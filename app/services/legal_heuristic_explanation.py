from __future__ import annotations

from app.domain.legal_heuristics import LegalHeuristicEvaluation


def build_heuristic_explanation_evidence(
    evaluation: LegalHeuristicEvaluation | None,
) -> tuple[list[str], list[str], bool]:
    """Proyecta heurísticas deterministas hacia explicación sin reinterpretarlas."""
    if evaluation is None:
        return [], [], False

    signals = [
        (
            f"{signal.code}|{signal.kind.value}|{signal.level.value}|"
            f"review={str(signal.requires_review).lower()}|{signal.message}"
        )
        for signal in evaluation.signals
    ]
    priorities = list(evaluation.analysis_priority)
    return signals, priorities, evaluation.requires_review
