from pathlib import Path

INDEX = Path("app/web/templates/index.html")
JS = Path("app/web/static/js/app.js")


def test_analyzer_1_0_summary_has_visual_contract() -> None:
    html = INDEX.read_text(encoding="utf-8")
    required_ids = (
        'id="analyzer-block"',
        'id="analyzer-status-badge"',
        'id="analyzer-primary-intent"',
        'id="analyzer-controlling-source"',
        'id="analyzer-conclusion"',
        'id="analyzer-audience"',
    )
    for identifier in required_ids:
        assert identifier in html


def test_frontend_consumes_legal_analysis_without_recalculating_it() -> None:
    javascript = JS.read_text(encoding="utf-8")
    assert "const analysis = result.legal_analysis;" in javascript
    assert "renderLegalAnalysis(result);" in javascript
    assert "analysis.canonical_conclusion" in javascript
    assert "analysis.controlling_source" in javascript
    assert "build_integral_legal_analysis" not in javascript


def test_visual_analyzer_exposes_all_three_application_modes() -> None:
    html = INDEX.read_text(encoding="utf-8")
    assert '<option value="taxpayer">Contribuyente</option>' in html
    assert '<option value="student">Estudiante</option>' in html
    assert '<option value="professional">Profesional</option>' in html
