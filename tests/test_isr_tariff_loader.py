from pathlib import Path

import pytest

from app.services.isr_tariff_loader import ISRTariffLoadError, load_isr_tariff


def test_load_fixture() -> None:
    path = Path("calculators/fixtures/isr_test_tariff.json")
    tariff = load_isr_tariff(path)
    assert tariff.version == "TEST-1.0"


def test_reject_non_json(tmp_path: Path) -> None:
    path = tmp_path / "tariff.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(ISRTariffLoadError):
        load_isr_tariff(path)
