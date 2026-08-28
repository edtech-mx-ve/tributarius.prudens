from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.security.dependencies import enforce_consultation_rate_limit, enforce_same_origin
from app.web.dependencies import get_web_consultation_service
from app.web.schemas import WebConsultationRequest, WebConsultationResponse
from app.web.service import WebConsultationService

router = APIRouter()
WEB_DIR = Path(__file__).resolve().parents[2] / "web"
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

WebService = Annotated[
    WebConsultationService,
    Depends(get_web_consultation_service),
]


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": "Tributarius prudens"},
    )


@router.post(
    "/api/v1/consultations",
    response_model=WebConsultationResponse,
    dependencies=[
        Depends(enforce_same_origin),
        Depends(enforce_consultation_rate_limit),
    ],
)
def create_consultation(
    payload: WebConsultationRequest,
    service: WebService,
) -> WebConsultationResponse:
    return service.consult(payload)
