from __future__ import annotations

import json

from app.domain.hybrid_legal_verification import HybridLegalVerificationPacket
from llm.hybrid_compact_contracts import compact_verification_packet

_F7_SYSTEM_PROMPT = """Eres el verificador híbrido F.7 de Tributarius prudens.
Audita únicamente el resumen controlado proporcionado. No resuelvas nuevamente la
consulta, no modifiques la conclusión canónica y no inventes hechos, normas,
jurisprudencia ni fuentes externas. RBS conserva prioridad determinativa; CBR es
sólo contraste experiencial; H1 y H2 son hipótesis no vinculantes. h2_assessments
es un objeto: usa exactamente las claves exigidas por el esquema ("0", "1", etc.),
una por cada H2 de packet.h2 y en la misma posición lógica. Si la evidencia
presentada es consistente,
marca consistent; usa unresolved sólo cuando exista una insuficiencia material real.
No reportes contradicciones o alucinaciones inexistentes. Si
binding_jurisprudence.applicable_document_ids está vacío, usa not_applicable para
binding_jurisprudence_consistency. Si no existe H1, usa not_applicable para
h1_consistency. Devuelve sólo JSON conforme al esquema solicitado.
"""


def build_f7_verification_messages(
    packet: HybridLegalVerificationPacket,
    *,
    packet_sha256: str,
) -> list[dict[str, str]]:
    compact_packet = compact_verification_packet(packet)
    generated_h2_count = len(compact_packet["h2"])
    payload = {
        "task": "verificar_argumento_hibrido_sin_redecidir",
        "packet_sha256_reference": packet_sha256,
        "expected_h2_assessment_count": generated_h2_count,
        "legal_boundary": {
            "external_sources_allowed": False,
            "may_change_canonical_conclusion": False,
            "rbs_priority_must_be_preserved": True,
            "cbr_is_experiential_only": True,
            "h2_source_section": "justification",
            "can_control_legal_decision": False,
        },
        "packet": compact_packet,
    }
    return [
        {"role": "system", "content": _F7_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]
