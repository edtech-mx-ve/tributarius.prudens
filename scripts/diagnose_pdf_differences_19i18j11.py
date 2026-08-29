from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_pdf_differential_diagnostic import (
    PdfDifferentialError,
    run_pdf_differential_diagnostic,
)

DEFAULT_LOCAL_BRIDGE = Path(
    "reports/sprint19I18I/runtime_source_bridge.json"
)
DEFAULT_BROWSER_MANIFEST = Path(
    "dist/browser_official_evidence_19i18j6/evidence_manifest.json"
)
DEFAULT_BROWSER_BRIDGE = Path(
    "reports/sprint19I18J7/browser_official_evidence_bridge.json"
)
DEFAULT_OUTPUT = Path(
    "reports/sprint19I18J11/pdf_differential_diagnostic.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18J.11: diagnostica diferencias entre PDFs "
            "oficiales y PDFs locales sin modificar el corpus."
        )
    )
    parser.add_argument(
        "--local-bridge", type=Path, default=DEFAULT_LOCAL_BRIDGE
    )
    parser.add_argument(
        "--browser-manifest", type=Path, default=DEFAULT_BROWSER_MANIFEST
    )
    parser.add_argument(
        "--browser-bridge", type=Path, default=DEFAULT_BROWSER_BRIDGE
    )
    parser.add_argument(
        "--local-corpus-dir",
        type=Path,
        default=None,
        help="Directorio opcional para resolver PDFs locales por SHA-256.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        report = run_pdf_differential_diagnostic(
            local_bridge_path=args.local_bridge,
            browser_manifest_path=args.browser_manifest,
            browser_bridge_path=args.browser_bridge,
            local_corpus_dir=args.local_corpus_dir,
            output_path=args.output,
        )
    except PdfDifferentialError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18J.11; diagnóstico diferencial completado")
    print(
        "- textually_equivalent_documents="
        f"{','.join(report['textually_equivalent_documents'])}"
    )
    print(
        "- manual_review_documents="
        f"{','.join(report['manual_review_documents'])}"
    )
    print(
        "- material_textual_difference_documents="
        f"{','.join(report['material_textual_difference_documents'])}"
    )
    print(f"- corpus_rebuild_required={report['corpus_rebuild_required']}")
    print("- official_provenance_promotion_performed=False")
    print("- public_release_allowed=False")
    print(f"- report={args.output}")

    for row in report["documents"]:
        print(
            f"  {row['document_id']}: "
            f"binary={row['exact_binary_match']}; "
            f"text={row['exact_normalized_text_match']}; "
            f"similarity={row['text_similarity']}; "
            f"pages_equal={row['page_count_equal']}; "
            f"classification={row['classification']}"
        )

    return 0 if not report["material_textual_difference_documents"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
