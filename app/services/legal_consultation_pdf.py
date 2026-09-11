from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

import reportlab  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import LETTER  # type: ignore[import-untyped]
from reportlab.lib.styles import (  # type: ignore[import-untyped]
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Paragraph,
    SimpleDocTemplate,
)

from app.domain.legal_consultation_report import LegalConsultationReport

_REGULAR = "TPVera"
_BOLD = "TPVeraBold"


class LegalConsultationPdfError(RuntimeError):
    """G.10: fallo controlado del render documental."""


def _ensure_fonts() -> None:
    registered = set(pdfmetrics.getRegisteredFontNames())
    if _REGULAR in registered and _BOLD in registered:
        return

    package_file = reportlab.__file__
    if package_file is None:
        raise LegalConsultationPdfError(
            "G.10 no pudo localizar ReportLab."
        )

    font_dir = Path(package_file).resolve().parent / "fonts"

    fonts = (
        (_REGULAR, font_dir / "Vera.ttf"),
        (_BOLD, font_dir / "VeraBd.ttf"),
    )

    for name, font_path in fonts:
        if not font_path.is_file():
            raise LegalConsultationPdfError(
                f"G.10 no encontro la fuente requerida: {font_path.name}"
            )

        if name not in registered:
            pdfmetrics.registerFont(
                TTFont(name, str(font_path))
            )


def _text(value: object) -> str:
    if value is None:
        return ""

    enum_value = getattr(value, "value", None)
    raw = (
        enum_value
        if isinstance(enum_value, str)
        else str(value)
    )

    return "".join(
        char
        if char in {"\n", "\t"} or ord(char) >= 32
        else " "
        for char in raw
    ).strip()


def _styles() -> dict[str, Any]:
    sample = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "TPTitle",
            parent=sample["Title"],
            fontName=_BOLD,
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "TPSubtitle",
            parent=sample["Normal"],
            fontName=_REGULAR,
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "heading": ParagraphStyle(
            "TPHeading",
            parent=sample["Heading2"],
            fontName=_BOLD,
            fontSize=11,
            leading=14,
            spaceBefore=9,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "TPBody",
            parent=sample["BodyText"],
            fontName=_REGULAR,
            fontSize=8.5,
            leading=12,
            spaceAfter=4,
            wordWrap="CJK",
        ),
        "label": ParagraphStyle(
            "TPLabel",
            parent=sample["BodyText"],
            fontName=_BOLD,
            fontSize=8.5,
            leading=11,
            spaceAfter=4,
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "TPSmall",
            parent=sample["BodyText"],
            fontName=_REGULAR,
            fontSize=7.2,
            leading=9.5,
            spaceAfter=3,
            wordWrap="CJK",
        ),
    }


def _add(
    story: list[Any],
    value: object,
    style: Any,
) -> None:
    text = _text(value) or "No disponible"

    story.append(
        Paragraph(
            escape(text).replace("\n", "<br/>"),
            style,
        )
    )


def _section(
    story: list[Any],
    number: int,
    title: str,
    styles: dict[str, Any],
) -> None:
    _add(
        story,
        f"{number}. {title}",
        styles["heading"],
    )


def _bullets(
    story: list[Any],
    values: list[str],
    styles: dict[str, Any],
) -> None:
    if not values:
        _add(story, "Ninguno.", styles["body"])
        return

    for value in values:
        _add(
            story,
            f"- {value}",
            styles["body"],
        )


def _canvasmaker(
    *args: Any,
    **kwargs: Any,
) -> Any:
    # invariant=1 evita fechas/IDs variables de ReportLab.
    # Esto sera importante para G.11.
    kwargs["invariant"] = 1

    pdf_canvas = Canvas(*args, **kwargs)
    pdf_canvas.setTitle(
        "Tributarius prudens - Informe de consulta juridica fiscal"
    )
    pdf_canvas.setAuthor("Tributarius prudens")
    pdf_canvas.setCreator("Tributarius prudens")

    return pdf_canvas


def _footer(
    pdf_canvas: Any,
    document: Any,
) -> None:
    pdf_canvas.saveState()
    pdf_canvas.setFont(_REGULAR, 7)

    pdf_canvas.drawString(
        document.leftMargin,
        10 * mm,
        "Tributarius prudens",
    )

    pdf_canvas.drawRightString(
        LETTER[0] - document.rightMargin,
        10 * mm,
        f"Pagina {document.page}",
    )

    pdf_canvas.restoreState()


def generate_legal_consultation_pdf(
    report: LegalConsultationReport,
) -> bytes:
    """Renderiza G.1-G.9 sin reejecutar razonamiento juridico."""

    _ensure_fonts()

    styles = _styles()
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    story: list[Any] = []

    _add(
        story,
        "TRIBUTARIUS PRUDENS",
        styles["title"],
    )
    _add(
        story,
        "INFORME DE CONSULTA JURIDICA FISCAL",
        styles["subtitle"],
    )

    configuration = report.query_configuration

    fiscal_year = (
        configuration.resolved_fiscal_year
        or configuration.requested_fiscal_year
        or "No especificado"
    )

    # 1
    _section(
        story,
        1,
        "Identificacion y configuracion",
        styles,
    )

    _bullets(
        story,
        [
            f"Folio: {report.folio}",
            f"Execution ID: {report.execution_id}",
            f"Fecha UTC: {report.created_at_utc.isoformat()}",
            (
                f"Modo: {configuration.explanation_mode.value} / "
                f"{report.mode_explanation.profile.audience_label}"
            ),
            f"Ejercicio fiscal: {fiscal_year}",
            f"Top K: {configuration.top_k}",
            f"SHA-256 canonico: {report.canonical_result_sha256}",
        ],
        styles,
    )

    # 2
    _section(
        story,
        2,
        "Consulta",
        styles,
    )
    _add(
        story,
        configuration.query,
        styles["body"],
    )

    # 3
    _section(
        story,
        3,
        "Ruta heuristica",
        styles,
    )

    route = report.heuristic_route

    if route is None:
        _add(
            story,
            "No se activo una ruta heuristica adicional.",
            styles["body"],
        )
    else:
        _add(
            story,
            (
                f"Fuente controladora: "
                f"{route.controlling_source or 'ninguna'}. "
                f"Revision: "
                f"{'SI' if route.requires_review else 'NO'}."
            ),
            styles["body"],
        )

        _bullets(
            story,
            [
                (
                    f"{signal.code} "
                    f"[{signal.level.value}] "
                    f"{signal.message}"
                )
                for signal in route.signals
            ],
            styles,
        )

    # 4
    _section(
        story,
        4,
        "RBS aplicado",
        styles,
    )

    matched_rules = (
        report.applied_rbs.rule_evaluation.matched_rules
    )

    if not matched_rules:
        _add(
            story,
            "No hubo reglas RBS coincidentes.",
            styles["body"],
        )

    for rule in matched_rules:
        _add(
            story,
            (
                f"- {rule.rule_id}@{rule.version} "
                f"[{rule.conclusion_code}] "
                f"{rule.conclusion}"
            ),
            styles["body"],
        )

        if rule.normative_refs:
            _add(
                story,
                "Fundamento: "
                + "; ".join(rule.normative_refs),
                styles["small"],
            )

    # 5
    _section(
        story,
        5,
        "CBR recuperado",
        styles,
    )

    retrieved_cbr = report.retrieved_cbr

    if (
        retrieved_cbr is None
        or retrieved_cbr.retrieval is None
    ):
        _add(
            story,
            "No se recuperaron casos CBR.",
            styles["body"],
        )
    else:
        _add(
            story,
            (
                f"Casos recuperados: "
                f"{retrieved_cbr.retrieval.returned_count}. "
                "Funcion exclusivamente analogica."
            ),
            styles["body"],
        )

        _bullets(
            story,
            [
                (
                    f"{match.case_id} | "
                    f"similitud={match.similarity:.3f} | "
                    f"{match.resolution_summary}"
                )
                for match in retrieved_cbr.retrieval.matches
            ],
            styles,
        )

    # 6
    _section(
        story,
        6,
        "Jurisprudencia de sesion",
        styles,
    )

    jurisprudence = report.session_jurisprudence

    if not jurisprudence.user_attached:
        _add(
            story,
            "No se adjunto jurisprudencia de sesion.",
            styles["body"],
        )
    else:
        _add(
            story,
            (
                "Jurisprudencia aportada por el usuario: SI. "
                f"Vinculante: "
                f"{'SI' if jurisprudence.binding_jurisprudence_applies else 'NO'}. "
                f"Interpretacion gobernante: "
                f"{'SI' if jurisprudence.governing_interpretation else 'NO'}."
            ),
            styles["body"],
        )

        if jurisprudence.applicable_document_ids:
            _bullets(
                story,
                list(
                    jurisprudence.applicable_document_ids
                ),
                styles,
            )

        for ratio in jurisprudence.ratio_records:
            if ratio.ratio_source_text:
                _add(
                    story,
                    (
                        f"Ratio {ratio.document_id}: "
                        f"{ratio.ratio_source_text}"
                    ),
                    styles["small"],
                )

    # 7
    _section(
        story,
        7,
        "Analisis juridico - Analyzer",
        styles,
    )

    analysis = report.analyzer

    _add(
        story,
        (
            f"Intent principal: "
            f"{analysis.issue.primary_intent.value}. "
            f"Estado: {analysis.status.value}."
        ),
        styles["body"],
    )

    if analysis.facts:
        _bullets(
            story,
            [
                (
                    f"{fact.name}: {fact.value} "
                    f"(origen={fact.origin.value})"
                )
                for fact in analysis.facts
            ],
            styles,
        )

    if analysis.calculation is not None:
        calculation = analysis.calculation

        _add(
            story,
            "Cálculo determinístico ISR:",
            styles["label"],
        )

        _bullets(
            story,
            [
                f"Base gravable acumulada: ${calculation.taxable_base:,.2f}",
                (
                    "ISR acumulado antes de pagos y retenciones: "
                    f"${calculation.tax_before_credits:,.2f}"
                ),
                (
                    "Pagos provisionales anteriores: "
                    f"${calculation.prior_provisional_payments:,.2f}"
                ),
                f"ISR retenido: ${calculation.isr_withholding:,.2f}",
                f"ISR provisional a pagar: ${calculation.final_tax:,.2f}",
                (
                    f"Tarifa: {calculation.tariff_version}; "
                    f"fundamento: {calculation.normative_ref}."
                ),
            ],
            styles,
        )

    if analysis.applicable_normative_refs:
        _add(
            story,
            "Base normativa aplicable:",
            styles["label"],
        )

        _bullets(
            story,
            list(analysis.applicable_normative_refs),
            styles,
        )

    # No imprimir analysis.canonical_conclusion aqui.
    _add(
        story,
        (
            "La conclusion canonica se omite en Analyzer "
            "para evitar duplicarla visualmente."
        ),
        styles["small"],
    )

    # 8
    _section(
        story,
        8,
        "Determinacion juridica",
        styles,
    )

    decision = report.legal_decision

    _add(
        story,
        (
            f"Estado: {decision.status.value}. "
            f"Fuente controladora: "
            f"{decision.controlling_source or 'ninguna'}."
        ),
        styles["body"],
    )

    hybrid_projection = getattr(
        decision,
        "hybrid_projection",
        None,
    )

    authority = getattr(
        hybrid_projection,
        "legal_authority_source",
        None,
    )

    if authority is not None:
        _add(
            story,
            f"Autoridad juridica: {_text(authority)}.",
            styles["body"],
        )

    _add(
        story,
        "CONCLUSION CANONICA",
        styles["label"],
    )

    _add(
        story,
        decision.conclusion
        or (
            "No se formalizo una conclusion porque "
            "el cierre juridico permanece bloqueado."
        ),
        styles["body"],
    )

    # 9
    _section(
        story,
        9,
        "Explicacion segun modo",
        styles,
    )

    mode_explanation = report.mode_explanation

    _add(
        story,
        (
            f"Modo: {mode_explanation.mode.value}. "
            f"Audiencia: "
            f"{mode_explanation.profile.audience_label}."
        ),
        styles["body"],
    )

    explanation = mode_explanation.explanation

    if explanation is None:
        _add(
            story,
            "No se produjo explicacion LLM.",
            styles["body"],
        )
    else:
        _add(
            story,
            (
                f"Proveedor: {explanation.provider_name}. "
                f"Modelo: {explanation.model_name}."
            ),
            styles["small"],
        )

        canonical_conclusion = (
            decision.conclusion or ""
        ).strip()

        if (
            explanation.answer.summary.strip()
            != canonical_conclusion
        ):
            _add(
                story,
                "Resumen:",
                styles["label"],
            )
            _add(
                story,
                explanation.answer.summary,
                styles["body"],
            )

        if (
            explanation.answer.analysis.strip()
            != canonical_conclusion
        ):
            _add(
                story,
                "Explicacion:",
                styles["label"],
            )
            _add(
                story,
                explanation.answer.analysis,
                styles["body"],
            )

        if explanation.answer.uncertainties:
            _add(
                story,
                "Incertidumbres:",
                styles["label"],
            )

            _bullets(
                story,
                list(
                    explanation.answer.uncertainties
                ),
                styles,
            )

    # 10
    _section(
        story,
        10,
        "Trazabilidad e integridad",
        styles,
    )

    _add(
        story,
        (
            "SHA-256 del resultado canonico: "
            f"{report.canonical_result_sha256}"
        ),
        styles["small"],
    )

    _bullets(
        story,
        [
            (
                f"{event.sequence}. "
                f"{_text(event.stage)} "
                f"[{_text(event.status)}] "
                f"{event.summary}"
            )
            for event in report.traceability.events
        ],
        styles,
    )

    document.build(
        story,
        onFirstPage=_footer,
        onLaterPages=_footer,
        canvasmaker=_canvasmaker,
    )

    pdf_bytes = buffer.getvalue()

    if not pdf_bytes.startswith(b"%PDF-"):
        raise LegalConsultationPdfError(
            "G.10 produjo una salida sin firma PDF valida."
        )

    return pdf_bytes
