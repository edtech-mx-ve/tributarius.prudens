from __future__ import annotations

from pathlib import Path

import pytest

from app.services import runtime_public_release_installer_19s_r4 as installer
from app.services.runtime_inner_integrity_19s_r10 import RuntimeInnerIntegrityError


def test_public_contract_runs_inner_integrity_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "candidate.zip"
    bundle.write_bytes(b"test")
    extracted = tmp_path / "extracted"
    calls: list[Path] = []

    monkeypatch.setattr(
        installer.cold_start,
        "validate_candidate_zip",
        lambda _: sorted(installer._PUBLIC_RUNTIME_FILES),
    )
    monkeypatch.setattr(
        installer.cold_start,
        "extract_candidate",
        lambda _bundle, destination: (destination / "runtime").mkdir(
            parents=True, exist_ok=True
        ),
    )
    monkeypatch.setattr(
        installer.cold_start, "verify_release_contract", lambda _: ({}, {})
    )
    monkeypatch.setattr(
        installer,
        "validate_runtime_inner_integrity",
        lambda runtime: calls.append(runtime) or {},
    )

    installer._validate_public_contract(bundle, extracted)

    assert calls == [extracted / "runtime"]


def test_inner_integrity_failure_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "candidate.zip"
    bundle.write_bytes(b"test")
    extracted = tmp_path / "extracted"

    monkeypatch.setattr(
        installer.cold_start,
        "validate_candidate_zip",
        lambda _: sorted(installer._PUBLIC_RUNTIME_FILES),
    )
    monkeypatch.setattr(
        installer.cold_start,
        "extract_candidate",
        lambda _bundle, destination: (destination / "runtime").mkdir(
            parents=True, exist_ok=True
        ),
    )
    monkeypatch.setattr(
        installer.cold_start, "verify_release_contract", lambda _: ({}, {})
    )

    def reject(_: Path) -> dict[str, int | str]:
        raise RuntimeInnerIntegrityError("SHA interno divergente")

    monkeypatch.setattr(installer, "validate_runtime_inner_integrity", reject)

    with pytest.raises(installer.RuntimeReleaseInstallError, match="SHA interno"):
        installer._validate_public_contract(bundle, extracted)
