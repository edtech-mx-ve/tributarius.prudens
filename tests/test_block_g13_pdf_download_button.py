from __future__ import annotations

from pathlib import Path

_TEMPLATE = Path("app/web/templates/index.html")
_SCRIPT = Path("app/web/static/js/app.js")


def _template() -> str:
    return _TEMPLATE.read_text(encoding="utf-8")


def _script() -> str:
    return _SCRIPT.read_text(encoding="utf-8")


def test_g13_exposes_single_pdf_download_control() -> None:
    html = _template()

    assert html.count('id="pdf-download-block"') == 1
    assert html.count('id="pdf-download-link"') == 1
    assert html.count('id="pdf-download-meta"') == 1

    assert "Reporte conclusivo en PDF" in html
    assert "Descargar PDF" in html
    assert 'class="button primary"' in html


def test_g13_consumes_only_g12_pdf_metadata() -> None:
    js = _script()

    assert js.count(
        "function renderPdfDownload(result)"
    ) == 1

    assert "result.pdf" in js
    assert "pdf.download_path" in js
    assert "pdf.filename" in js
    assert "pdf.sha256" in js

    assert js.count(
        "renderPdfDownload(result);"
    ) == 1


def test_g13_accepts_only_expected_same_origin_pdf_path() -> None:
    js = _script()

    expected = (
        r"^\/api\/v1\/consultations\/"
        r"TP-[A-F0-9]{32}\/pdf$"
    )

    assert expected in js


def test_g13_does_not_regenerate_or_refetch_consultation() -> None:
    js = _script()

    start = js.index(
        "function renderPdfDownload(result)"
    )
    end = js.index(
        "function renderResult(payload)",
        start,
    )

    helper = js[start:end]

    assert 'fetch(' not in helper
    assert "/api/v1/consultations\"" not in helper
    assert "build_legal_consultation" not in helper
    assert "generate" not in helper.casefold()


def test_g13_download_control_fails_closed_without_valid_path() -> None:
    js = _script()

    assert "block.hidden = true;" in js
    assert 'link.removeAttribute("href");' in js
    assert 'link.removeAttribute("download");' in js
    assert "block.hidden = false;" in js
