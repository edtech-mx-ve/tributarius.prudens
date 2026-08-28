from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import database_session
from app.domain.deployment import ReadinessReport, ReadinessState
from app.schemas.health import HealthResponse
from app.services.runtime_readiness import build_readiness_report

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    database_status = "ok"
    try:
        with database_session() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    status = "ok" if database_status == "ok" else "degraded"
    return HealthResponse(
        status=status,
        service="tributarius-prudens",
        database=database_status,
    )


@router.get("/ready", response_model=ReadinessReport)
def readiness(response: Response) -> ReadinessReport:
    report = build_readiness_report(get_settings())
    if report.state == ReadinessState.NOT_READY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
