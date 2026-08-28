from __future__ import annotations

import json
from pathlib import Path

from evaluation.error_analysis import analyze_errors
from evaluation.models import IntegralEvaluationReport


class EvaluationReportError(ValueError):
    pass


def export_evaluation_report(
    report: IntegralEvaluationReport,
    output_path: Path,
    *,
    overwrite: bool = False,
) -> Path:
    if output_path.suffix.lower() != ".json":
        raise EvaluationReportError("El reporte debe usar extensión .json.")
    if output_path.exists() and not overwrite:
        raise EvaluationReportError("El reporte ya existe; no se sobrescribe por defecto.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json")
    payload["error_analysis"] = analyze_errors(report).model_dump(mode="json")
    temporary = output_path.with_suffix(".json.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise EvaluationReportError("No fue posible escribir el reporte.") from exc
    return output_path
