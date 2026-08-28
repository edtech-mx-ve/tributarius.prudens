from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Contrato del endpoint de salud."""

    status: Literal["ok", "degraded"]
    service: str
    database: Literal["ok", "error"]
