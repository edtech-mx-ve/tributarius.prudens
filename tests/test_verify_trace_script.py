from pathlib import Path

from app.services.traceability import verify_canonical_integrity
from scripts.verify_trace import load_trace


def test_synthetic_trace_fixture_is_valid() -> None:
    trace = load_trace(Path("traceability/fixtures/trace_test.json"))
    assert verify_canonical_integrity(trace) is True
