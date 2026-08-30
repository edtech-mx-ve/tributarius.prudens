from __future__ import annotations

import importlib.metadata
import os
from collections.abc import Iterable

_FORBIDDEN_PREFIXES = ("nvidia-", "cuda-")
_FORBIDDEN_EXACT = frozenset({"triton"})


class CpuRuntimeValidationError(RuntimeError):
    """El entorno de despliegue CPU contiene dependencias aceleradoras no permitidas."""


def forbidden_accelerator_packages(names: Iterable[str]) -> list[str]:
    normalized = {name.strip().casefold() for name in names if name.strip()}
    return sorted(
        name
        for name in normalized
        if name in _FORBIDDEN_EXACT
        or any(name.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES)
    )


def installed_distribution_names() -> list[str]:
    names: list[str] = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if isinstance(name, str) and name.strip():
            names.append(name)
    return names


def validate_cpu_runtime_environment() -> None:
    profile = os.environ.get("RUNTIME_PROFILE", "").strip().casefold()
    backend = os.environ.get("RAG_RUNTIME_BACKEND", "").strip().casefold()

    if profile != "stateless_free":
        raise CpuRuntimeValidationError(
            "RUNTIME_PROFILE debe ser stateless_free para este gate."
        )
    if backend != "lexical_cpu":
        raise CpuRuntimeValidationError(
            "RAG_RUNTIME_BACKEND debe ser lexical_cpu para Render Free."
        )

    forbidden = forbidden_accelerator_packages(installed_distribution_names())
    if forbidden:
        raise CpuRuntimeValidationError(
            "Dependencias GPU/CUDA detectadas en runtime CPU: "
            + ", ".join(forbidden)
        )

    try:
        import torch
    except ImportError as exc:
        raise CpuRuntimeValidationError("Torch CPU no está instalado.") from exc

    if torch.cuda.is_available():
        raise CpuRuntimeValidationError(
            "CUDA aparece disponible en un runtime declarado CPU-only."
        )


def main() -> int:
    try:
        validate_cpu_runtime_environment()
    except CpuRuntimeValidationError as exc:
        print(f"ERROR: {exc}")
        return 1
    print("OK: runtime CPU-only validado; sin dependencias CUDA/NVIDIA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
