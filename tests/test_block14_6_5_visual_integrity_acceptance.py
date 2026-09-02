from pathlib import Path

CSS = Path("app/web/static/css/app.css")
INDEX = Path("app/web/templates/index.html")
JS = Path("app/web/static/js/app.js")


def test_analyzer_integrity_hash_is_exposed_separately() -> None:
    html = INDEX.read_text(encoding="utf-8")
    javascript = JS.read_text(encoding="utf-8")
    assert 'id="analyzer-integrity-hash"' in html
    assert "analysis.integrity_sha256" in javascript
    assert 'id="result-result-hash"' in html


def test_visual_analyzer_degrades_gracefully_when_field_is_absent() -> None:
    javascript = JS.read_text(encoding="utf-8")
    assert 'if (!analysis || typeof analysis !== "object") {' in javascript
    assert "block.hidden = true;" in javascript


def test_analyzer_visual_styles_cover_status_and_evidence_states() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert ".analyzer-status.ready" in css
    assert ".analyzer-status.review_required" in css
    assert ".analyzer-status.insufficient_evidence" in css
    assert ".presence-badge.present" in css
    assert ".presence-badge.absent" in css
    assert ".analyzer-card.complete" in css
    assert ".analyzer-card.missing" in css
