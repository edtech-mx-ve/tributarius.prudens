import json
from pathlib import Path

import pytest

from app.services.rule_loader import RuleLoadError, load_rule_set


def test_load_valid_rule_set(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "rules": [{
                    "rule_id": "RULE_TEST_001",
                    "version": "1.0",
                    "description": "Prueba.",
                    "conditions": [{"fact": "active", "operator": "eq", "value": True}],
                    "conclusion_code": "active",
                    "conclusion": "Activo."
                }]
            }
        ),
        encoding="utf-8",
    )
    assert load_rule_set(path).rules[0].rule_id == "RULE_TEST_001"


def test_reject_non_json(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text("rules: []", encoding="utf-8")
    with pytest.raises(RuleLoadError):
        load_rule_set(path)


def test_reject_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(RuleLoadError):
        load_rule_set(path)
