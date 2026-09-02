from pathlib import Path

from app.web.schemas import WebConsultationRequest


def test_web_exposes_only_student_and_professional_llama_modes() -> None:
    html = Path("app/web/templates/index.html").read_text(encoding="utf-8")

    assert '<option value="professional">Profesional</option>' in html
    assert '<option value="student">Estudiante</option>' in html
    assert '<option value="taxpayer">' not in html
    assert "Modo de explicación de Llama" in html


def test_web_explains_that_mode_does_not_change_legal_reasoning() -> None:
    html = Path("app/web/templates/index.html").read_text(encoding="utf-8")

    assert "no la evidencia ni la conclusión jurídica" in html


def test_existing_web_contract_accepts_student_and_professional_modes() -> None:
    student = WebConsultationRequest(
        query="Explícame el tratamiento fiscal.",
        mode="student",
    )
    professional = WebConsultationRequest(
        query="Analiza el tratamiento fiscal.",
        mode="professional",
    )

    assert student.mode == "student"
    assert professional.mode == "professional"
