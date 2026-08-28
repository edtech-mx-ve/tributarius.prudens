from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.core.config import get_settings
from app.core.database import database_session
from app.core.logging import configure_logging
from app.services.knowledge_matrix import KnowledgeMatrixError, load_matrix_file, persist_matrix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida y carga la Matriz Maestra Jurídico-Fiscal."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("knowledge/metadata/master_matrix.json"),
        help="Archivo JSON de la matriz.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(get_settings().log_level)

    try:
        entries = load_matrix_file(args.input)
        with database_session() as session:
            persisted = persist_matrix(session, entries)
    except (KnowledgeMatrixError, ValueError) as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1

    print("Matriz Maestra cargada correctamente")
    print(f"Módulos procesados: {len(persisted)}")
    for entry in persisted:
        print(f"- {entry.module_key}: {entry.module_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
