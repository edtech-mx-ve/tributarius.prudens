from __future__ import annotations

import hashlib
import json

from app.domain.cbr import CaseStatus, CBRCase, CBRRetentionCandidate


def create_retention_candidate(
    case: CBRCase,
    *,
    utility_reason: str,
) -> CBRRetentionCandidate:
    """Crea un candidato pendiente; nunca activa casos automáticamente."""
    payload = json.dumps(
        case.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16].upper()

    proposed = case.model_copy(update={"status": CaseStatus.HISTORICAL})
    return CBRRetentionCandidate(
        candidate_id=f"CBRCAND-{digest}",
        proposed_case=proposed,
        utility_reason=utility_reason,
    )
