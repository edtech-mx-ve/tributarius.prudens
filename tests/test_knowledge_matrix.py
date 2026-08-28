import json
from pathlib import Path

import pytest

from app.services.knowledge_matrix import KnowledgeMatrixError, load_matrix_file


def test_load_matrix_file_validates_entries(tmp_path: Path) -> None:
    path = tmp_path / "matrix.json"
    path.write_text(
        json.dumps(
            [
                {
                    "module_key": "derechos",
                    "module_name": "Conocer derechos",
                    "prodecon_refs": ["por_mapear"],
                    "normative_refs": ["por_mapear"],
                }
            ]
        ),
        encoding="utf-8",
    )

    entries = load_matrix_file(path)
    assert len(entries) == 1
    assert entries[0].module_key == "derechos"


def test_load_matrix_file_rejects_duplicate_module_keys(tmp_path: Path) -> None:
    path = tmp_path / "matrix.json"
    path.write_text(
        json.dumps(
            [
                {"module_key": "isr", "module_name": "ISR"},
                {"module_key": "isr", "module_name": "ISR duplicado"},
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeMatrixError, match="duplicados"):
        load_matrix_file(path)
