from __future__ import annotations

import os
from unittest.mock import patch

import scripts.bootstrap_runtime_release_19i18c as bootstrap


def test_bootstrap_fails_closed_without_required_env() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert bootstrap.main() == 1


def test_bootstrap_rejects_non_https_source() -> None:
    with patch.dict(
        os.environ,
        {
            "RUNTIME_RELEASE_URL": "http://example.invalid/runtime.zip",
            "RUNTIME_RELEASE_SHA256": "0" * 64,
        },
        clear=True,
    ):
        assert bootstrap.main() == 1
