from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MASTER_MATRIX_PATH = PROJECT_ROOT / "knowledge" / "metadata" / "master_matrix.json"

PLACEHOLDERS = {
    "por_mapear",
    "por_definir",
    "opcional_por_mapear",
    "isr_basico_por_definir",
    "iva_por_definir",
}

EXPECTED_MODULE_KEYS = {
    "entender_sistema_fiscal",
    "identificar_obligaciones",
    "conocer_derechos",
    "calcular_isr",
    "calcular_iva",
    "analizar_actos_autoridad",
    "opciones_defensa",
    "interpretar_disposiciones",
}

KNOWN_PRODECON_REFS = {f"PRODECON-{index:02d}" for index in range(1, 13)}

KNOWN_UNAM_REFS = {
    "Capítulo I",
    "Capítulo II",
    "Capítulo III",
    "Capítulo IV",
    "Capítulo V",
    "Capítulo VI",
    "Capítulo VII",
}

KNOWN_NORMATIVE_REFS = {
    "cpeum",
    "cff",
    "lfdc",
    "lisr",
    "liva",
    "reg_cff",
    "reg_lisr_060516",
    "reg_liva_250914",
    "rmf_2026",
    "lif_2026",
    "lfpca",
    "lotfja",
    "lieps",
    "lfisan",
}


class MatrixEntry(TypedDict):
    module_key: str
    module_name: str
    prodecon_refs: list[str]
    unam_refs: list[str]
    normative_refs: list[str]
    jurisprudential_refs: list[str]
    rule_refs: list[str]
    calculation_refs: list[str]
    cbr_refs: list[str]
    notes: str


def _load_matrix() -> list[MatrixEntry]:
    payload = json.loads(MASTER_MATRIX_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return payload


def test_master_matrix_has_expected_modules_without_placeholders() -> None:
    matrix = _load_matrix()
    assert {entry["module_key"] for entry in matrix} == EXPECTED_MODULE_KEYS

    serialized = json.dumps(matrix, ensure_ascii=False)
    for placeholder in PLACEHOLDERS:
        assert placeholder not in serialized


def test_master_matrix_uses_known_source_references() -> None:
    matrix = _load_matrix()

    for entry in matrix:
        assert set(entry["prodecon_refs"]) <= KNOWN_PRODECON_REFS
        assert set(entry["unam_refs"]) <= KNOWN_UNAM_REFS
        assert set(entry["normative_refs"]) <= KNOWN_NORMATIVE_REFS

        assert entry["prodecon_refs"]
        assert entry["unam_refs"]
        assert entry["normative_refs"]

        assert entry["jurisprudential_refs"] == []
        assert entry["rule_refs"] == []
        assert entry["calculation_refs"] == []
        assert entry["cbr_refs"] == []


def test_master_matrix_keeps_transversal_source_separation() -> None:
    by_key = {entry["module_key"]: entry for entry in _load_matrix()}

    assert by_key["interpretar_disposiciones"]["prodecon_refs"] == [
        "PRODECON-02",
        "PRODECON-09",
    ]
    assert by_key["interpretar_disposiciones"]["unam_refs"] == [
        "Capítulo I",
        "Capítulo II",
    ]
    assert by_key["interpretar_disposiciones"]["normative_refs"] == [
        "cpeum",
        "cff",
    ]

    assert by_key["calcular_isr"]["prodecon_refs"] == [
        "PRODECON-05",
        "PRODECON-10",
        "PRODECON-11",
        "PRODECON-12",
    ]
    assert by_key["calcular_isr"]["unam_refs"] == ["Capítulo V"]
    assert by_key["calcular_isr"]["normative_refs"] == [
        "lisr",
        "reg_lisr_060516",
        "rmf_2026",
        "lif_2026",
    ]

    assert by_key["opciones_defensa"]["prodecon_refs"] == [
        "PRODECON-07",
        "PRODECON-08",
    ]
    assert by_key["opciones_defensa"]["normative_refs"] == [
        "cpeum",
        "cff",
        "lfdc",
        "lfpca",
        "lotfja",
    ]
