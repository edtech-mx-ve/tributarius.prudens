from __future__ import annotations

from functools import lru_cache

from app.web.service import WebConsultationService


@lru_cache
def get_web_consultation_service() -> WebConsultationService:
    """Runtime web seguro por defecto: sin backend ficticio."""
    return WebConsultationService()
