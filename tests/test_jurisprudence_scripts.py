import subprocess
import sys


def test_validate_jurisprudence_metadata_script() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.validate_jurisprudence_metadata",
            "--metadata",
            "jurisprudence/fixtures/metadata_synthetic.jsonl",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "OK: 3 registros jurisprudenciales" in result.stdout


def test_assess_jurisprudence_candidates_script() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.assess_jurisprudence_candidates",
            "--metadata",
            "jurisprudence/fixtures/metadata_synthetic.jsonl",
            "--query-date",
            "2026-08-28",
            "--norm-ref",
            "NORM_TEST_ISR_2026",
            "--matter",
            "fiscal",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert '"candidate_count": 3' in result.stdout
    assert '"eligible_count": 2' in result.stdout
