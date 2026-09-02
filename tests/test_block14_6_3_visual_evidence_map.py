from pathlib import Path

INDEX = Path("app/web/templates/index.html")
JS = Path("app/web/static/js/app.js")


def test_integrated_evidence_map_has_dedicated_surface() -> None:
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="analyzer-evidence-map"' in html
    assert "Mapa de evidencia integrada" in html


def test_all_five_analyzer_evidence_channels_are_renderable() -> None:
    javascript = JS.read_text(encoding="utf-8")
    expected = {
        'normative: "Normativa"',
        'rbs: "RBS"',
        'cbr: "CBR"',
        'jurisprudence: "Jurisprudencia"',
        'calculation: "Cálculo"',
    }
    for channel in expected:
        assert channel in javascript
    assert 'item.present ? "Presente" : "No aportada"' in javascript
    assert "item.references" in javascript
