from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_factory_uses_runtime_query_analyzer_not_test_mock() -> None:
    source = (ROOT / "app/services/runtime_factory.py").read_text(encoding="utf-8")

    assert "RuntimeQueryAnalyzerProvider" in source
    assert "MockQueryAnalyzerProvider" not in source
