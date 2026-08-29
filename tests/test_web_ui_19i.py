from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_19i_template_contains_accessible_evidence_and_trace_sections() -> None:
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")

    assert 'id="normative-evidence-group"' in template
    assert 'id="supporting-evidence-group"' in template
    assert 'id="jurisprudence-evidence-group"' in template
    assert 'id="trace-block"' in template
    assert "Ver etapas de razonamiento" in template
    assert "Huella del resultado" in template


def test_19i_javascript_renders_with_text_content_not_inner_html() -> None:
    script = (ROOT / "app/web/static/js/app.js").read_text(encoding="utf-8")

    assert "renderEvidenceCard" in script
    assert "renderTraceability" in script
    assert ".textContent" in script
    assert ".innerHTML" not in script
    assert "result.requires_human_review" in script


def test_19i_css_has_mobile_and_reduced_motion_rules() -> None:
    css = (ROOT / "app/web/static/css/app.css").read_text(encoding="utf-8")

    assert ".evidence-card" in css
    assert ".trace-events" in css
    assert "@media (max-width: 42rem)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
