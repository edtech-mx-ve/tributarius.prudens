from pathlib import Path

INDEX = Path("app/web/templates/index.html")
JS = Path("app/web/static/js/app.js")


def test_priorities_and_pending_analysis_have_visual_sections() -> None:
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="analyzer-priority-block"' in html
    assert 'id="analyzer-priorities"' in html
    assert 'id="analyzer-pending-block"' in html
    assert 'id="analyzer-pending"' in html


def test_pending_surface_preserves_missing_ambiguity_and_review() -> None:
    javascript = JS.read_text(encoding="utf-8")
    assert "analysis.missing_fields" in javascript
    assert "analysis.ambiguities" in javascript
    assert "readiness.missing_requirements" in javascript
    assert "analysis.requires_human_review" in javascript
    assert "analysis.analysis_priority" in javascript
