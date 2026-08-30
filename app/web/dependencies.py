from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import get_settings
from app.services.runtime_factory import RuntimeBuildError, build_runtime_components
from app.web.service import WebConsultationService

logger = logging.getLogger(__name__)


@lru_cache
def get_web_consultation_service() -> WebConsultationService:
    """Construye el runtime real si los artefactos están disponibles."""
    try:
        components = build_runtime_components(get_settings())
    except RuntimeBuildError as exc:
        logger.warning(
            "Runtime de consulta no configurado; se mantiene degradación segura. "
            "cause_type=%s cause=%s",
            type(exc).__name__,
            str(exc),
        )
        return WebConsultationService()
    return WebConsultationService(components.runner)
