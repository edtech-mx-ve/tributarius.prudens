from __future__ import annotations

import errno
from pathlib import Path

import pytest

from app.services import runtime_public_release_installer_19s_r4 as installer


def test_replace_tree_does_not_rename_source_across_filesystems(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "tmpfs" / "runtime"
    destination = tmp_path / "project" / "runtime"
    source.mkdir(parents=True)
    destination.mkdir(parents=True)
    (source / "new.txt").write_text("new", encoding="utf-8")
    (destination / "old.txt").write_text("old", encoding="utf-8")

    original_replace = Path.replace

    def guarded_replace(self: Path, target: Path) -> Path:
        if self == source:
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", guarded_replace)

    installer._replace_tree(source, destination)

    assert (destination / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (destination / "old.txt").exists()
    assert source.is_dir()
    assert not destination.with_name(".runtime.staged").exists()
    assert not destination.with_name(".runtime.backup").exists()
