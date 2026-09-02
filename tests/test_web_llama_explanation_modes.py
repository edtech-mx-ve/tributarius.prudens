from pathlib import Path

from app.web.schemas import WebConsultationRequest


def test_web_exposes_all_three_application_modes() -> None:
    html = Path("app/web/templates/index.html").read_text(encoding="utf-8")

    assert '<option value="taxpayer">Contribuyente</option>' in html
    assert '<option value="student">Estudiante</option>' in html
    assert '<option value="professional">Profesional</option>' in html
    assert "Modo de aplicación" in html


def test_web_explains_that_mode_does_not_change_legal_reasoning() -> None:
    html = Path("app/web/templates/index.html").read_text(encoding="utf-8")

    assert "no la evidencia ni la conclusión jurídica" in html


def test_web_contract_accepts_all_three_application_modes() -> None:
    taxpayer = WebConsultationRequest(
        query="Explícame qué debo hacer.",
        mode="taxpayer",
    )
    student = WebConsultationRequest(
        query="Explícame el tratamiento fiscal.",
        mode="student",
    )
    professional = WebConsultationRequest(
        query="Analiza el tratamiento fiscal.",
        mode="professional",
    )

    assert taxpayer.mode == "taxpayer"
    assert student.mode == "student"
    assert professional.mode == "professional"
