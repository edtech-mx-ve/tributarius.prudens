from __future__ import annotations

import json
from pathlib import Path

POLICY_PATH = Path("app/resources/legal_retrieval_policy.json")

EXPECTED_NORMATIVE_ALIASES = {
    "cpeum": {"cpeum"},
    "cff": {"cff"},
    "lfdc": {"lfdc"},
    "lisr": {"lisr", "isr"},
    "liva": {"liva", "iva"},
    "reg_cff": {"rcff"},
    "reg_lisr_060516": {"rlisr"},
    "reg_liva_250914": {"rliva"},
    "rmf_2026": {"rmf", "rmf 2026"},
    "lif_2026": {"lif", "lif 2026"},
    "lfpca": {"lfpca"},
    "lotfja": {"lotfja"},
    "lieps": {"lieps", "ieps"},
    "lfisan": {"lfisan", "isan"},
}


def _routes() -> dict[str, set[str]]:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return {
        route["document_id"]: {alias.casefold() for alias in route["aliases"]}
        for route in payload["document_routes"]
    }


def test_policy_routes_all_fourteen_normative_sources() -> None:
    routes = _routes()
    assert set(EXPECTED_NORMATIVE_ALIASES) <= set(routes)


def test_policy_exposes_canonical_legal_abbreviations() -> None:
    routes = _routes()
    for document_id, expected_aliases in EXPECTED_NORMATIVE_ALIASES.items():
        assert expected_aliases <= routes[document_id]
