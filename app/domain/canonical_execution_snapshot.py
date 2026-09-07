from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CanonicalExecutionSnapshot(BaseModel):
    """G.2: snapshot inmutable de una ejecucion canonica ya calculada."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    execution_id: str = Field(pattern=r"^TP-[A-F0-9]{32}$")
    folio: str = Field(pattern=r"^TP-\d{8}-[A-F0-9]{12}$")
    created_at_utc: datetime
    source_canonical_result_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    canonical_json: str = Field(min_length=2)
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    source_results_already_computed: Literal[True] = True
    source_result_reexecuted: Literal[False] = False
    can_change_canonical_conclusion: Literal[False] = False

    @model_validator(mode="after")
    def validate_snapshot(self) -> CanonicalExecutionSnapshot:
        expected_sha = hashlib.sha256(
            self.canonical_json.encode("utf-8")
        ).hexdigest()
        if self.snapshot_sha256 != expected_sha:
            raise ValueError("G.2 detecto una huella de snapshot inconsistente.")

        try:
            payload = json.loads(self.canonical_json)
        except json.JSONDecodeError as exc:
            raise ValueError("G.2 exige JSON canonico valido.") from exc

        if not isinstance(payload, dict):
            raise ValueError("G.2 exige un objeto JSON canonico.")

        if payload.get("execution_id") != self.execution_id:
            raise ValueError("G.2 detecto un execution_id inconsistente.")

        if payload.get("folio") != self.folio:
            raise ValueError("G.2 detecto un folio inconsistente.")

        raw_created_at = payload.get("created_at_utc")
        if not isinstance(raw_created_at, str):
            raise ValueError("G.2 exige created_at_utc en el snapshot.")

        parsed_created_at = datetime.fromisoformat(
            raw_created_at.replace("Z", "+00:00")
        )
        if parsed_created_at != self.created_at_utc:
            raise ValueError("G.2 detecto una fecha de ejecucion inconsistente.")

        traceability = payload.get("traceability")
        if not isinstance(traceability, dict):
            raise ValueError("G.2 exige trazabilidad canonica.")

        if (
            traceability.get("canonical_result_sha256")
            != self.source_canonical_result_sha256
        ):
            raise ValueError(
                "G.2 no permite desacoplar el snapshot de su resultado canonico."
            )

        return self
