from scripts.audit_github_publish import _blocked_by_path


def test_production_cbr_corpus_is_publication_allowed() -> None:
    assert (
        _blocked_by_path(
            "cbr/data/production_cases.jsonl"
        )
        is None
    )


def test_other_cbr_data_files_remain_blocked() -> None:
    assert _blocked_by_path(
        "cbr/data/unreviewed_cases.jsonl"
    ) == "ruta privada/generada: cbr/data/"


def test_cbr_gitkeep_remains_allowed() -> None:
    assert _blocked_by_path("cbr/data/.gitkeep") is None
