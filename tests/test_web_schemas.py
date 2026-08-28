import pytest
from pydantic import ValidationError

from app.web.schemas import WebConsultationRequest


def test_query_is_trimmed() -> None:
    request = WebConsultationRequest(query="  consulta fiscal  ")
    assert request.query == "consulta fiscal"


def test_invalid_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        WebConsultationRequest(query="consulta", mode="invented")


def test_fiscal_year_range_is_validated() -> None:
    with pytest.raises(ValidationError):
        WebConsultationRequest(query="consulta", fiscal_year=1800)
