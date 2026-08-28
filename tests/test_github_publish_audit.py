from pathlib import Path

from scripts.audit_github_publish import _blocked_by_path, _scan_text


def test_private_and_generated_paths_are_blocked() -> None:
    assert _blocked_by_path(".env") is not None
    assert _blocked_by_path("secrets-prod.json") is not None
    assert _blocked_by_path("knowledge/sources/normativa/ley.pdf") is not None
    assert _blocked_by_path("knowledge/chunks/normativa/chunks.jsonl") is not None
    assert _blocked_by_path("deployment/runtime_artifacts/index.faiss") is not None
    assert _blocked_by_path("traceability/exports/case.json") is not None
    assert _blocked_by_path("model.gguf") is not None


def test_public_templates_and_structure_are_allowed() -> None:
    assert _blocked_by_path(".env.example") is None
    assert _blocked_by_path("knowledge/sources/normativa/.gitkeep") is None
    assert _blocked_by_path("deployment/runtime_artifacts/README.md") is None


def test_secret_pattern_is_detected(tmp_path: Path) -> None:
    candidate = tmp_path / "bad.txt"
    candidate.write_text(
        "token=" + "github_" + "pat_" + "1234567890ABCDEFGHIJKLMN",
        encoding="utf-8",
    )
    findings = _scan_text(candidate, "bad.txt")
    assert any(item.kind == "possible_secret" for item in findings)


def test_local_user_path_is_detected(tmp_path: Path) -> None:
    candidate = tmp_path / "bad.md"
    windows_path = "C:" + "\\" + "Users" + "\\" + "private-user" + "\\" + "secret.txt"
    candidate.write_text(
        "Ruta: " + windows_path,
        encoding="utf-8",
    )
    findings = _scan_text(candidate, "bad.md")
    assert any(item.kind == "local_path" for item in findings)
