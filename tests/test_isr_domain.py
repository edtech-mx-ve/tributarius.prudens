from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.isr import ISRBracket, ISRPeriod, ISRTariff


def test_unverified_tariff_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ISRTariff(
            schema_version="1.0",
            version="X",
            fiscal_year=2026,
            period=ISRPeriod.ANNUAL,
            normative_ref="NORM",
            source_reference="SOURCE",
            verified=False,
            brackets=[
                ISRBracket(
                    lower_limit=Decimal("0"),
                    upper_limit=None,
                    fixed_fee=Decimal("0"),
                    rate_percent=Decimal("1"),
                )
            ],
        )
