from app.services.query_fact_compat_19s_r15 import query_fact_value


class Fact:
    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value


def test_query_fact_value_accepts_mapping() -> None:
    assert query_fact_value([{"name": "matter", "value": "IVA"}], "matter") == "IVA"


def test_query_fact_value_accepts_model_like_object() -> None:
    assert query_fact_value([Fact("matter", "ISR")], "matter") == "ISR"


def test_query_fact_value_is_fail_closed_for_malformed_fact() -> None:
    assert query_fact_value([{"value": "IVA"}, object()], "matter") is None
