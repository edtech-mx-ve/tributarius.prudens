from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.normative import NormativeApplicabilityRequest


def test_invalid_interval_rejected() -> None:
    with pytest.raises(ValidationError):
        NormativeApplicabilityRequest(
            legal_unit_id=1,
            version_label="bad",
            effective_from=date(2026, 5, 1),
            effective_to=date(2026, 4, 1),
            query_date=date(2026, 5, 15),
        )
