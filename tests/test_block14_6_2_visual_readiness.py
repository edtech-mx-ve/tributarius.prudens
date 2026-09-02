from pathlib import Path

INDEX = Path("app/web/templates/index.html")
JS = Path("app/web/static/js/app.js")


def test_readiness_visual_surface_exists() -> None:
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="analyzer-readiness"' in html
    assert 'id="analyzer-sufficiency"' in html
    assert 'id="analyzer-auto-close"' in html


def test_readiness_uses_backend_completeness_states() -> None:
    javascript = JS.read_text(encoding="utf-8")
    for state in ("complete", "partial", "missing", "not_applicable"):
        assert f'{state}:' in javascript
    assert "readiness.completeness" in javascript
    assert "readiness.evidentiary_sufficiency" in javascript
    assert "readiness.can_close_automatically" in javascript
