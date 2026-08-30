from __future__ import annotations

from scripts.verify_cpu_runtime_19s_r14 import forbidden_accelerator_packages


def test_forbidden_accelerator_packages_detects_cuda_stack() -> None:
    result = forbidden_accelerator_packages(
        [
            "fastapi",
            "torch",
            "nvidia-cublas-cu13",
            "cuda-toolkit",
            "triton",
        ]
    )
    assert result == ["cuda-toolkit", "nvidia-cublas-cu13", "triton"]


def test_forbidden_accelerator_packages_allows_cpu_stack() -> None:
    assert forbidden_accelerator_packages(
        ["torch", "sentence-transformers", "faiss-cpu", "numpy"]
    ) == []
