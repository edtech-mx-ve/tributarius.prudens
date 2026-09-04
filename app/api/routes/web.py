from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.security.dependencies import enforce_consultation_rate_limit, enforce_same_origin
from app.web.dependencies import get_web_consultation_service
from app.web.jurisprudence_upload import (
    WebJurisprudenceUploadError,
    process_web_jurisprudence_upload,
)
from app.web.schemas import (
    WebConsultationRequest,
    WebConsultationResponse,
    WebJurisprudenceUploadResponse,
)
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
    "/api/v1/jurisprudence/session",
    response_model=WebJurisprudenceUploadResponse,
    dependencies=[Depends(enforce_same_origin)],
)
async def upload_session_jurisprudence(
    request: Request,
    x_filename: Annotated[str, Header(min_length=1, max_length=500)],
) -> WebJurisprudenceUploadResponse:
    content = await request.body()
    try:
        session_id, representation, metadata, ingestion_receipt = (
            process_web_jurisprudence_upload(
                content=content,
                filename=x_filename,
            )
        )
    except WebJurisprudenceUploadError as exc:
        return WebJurisprudenceUploadResponse(
            status="error",
            message=str(exc),
        )

    return WebJurisprudenceUploadResponse(
        status="ready",
        message="PDF jurisprudencial procesado como evidencia temporal.",
        session_id=session_id,
        document_id=representation.document_id,
        filename=representation.original_filename,
        page_count=representation.page_count,
        warnings=[*representation.warnings, *metadata.warnings],
        extracted_metadata=metadata.model_dump(mode="json"),
        sha256=ingestion_receipt.source_sha256,
        chunk_count=ingestion_receipt.chunk_count,
        source_scope=ingestion_receipt.source_scope.value,
        user_attached=ingestion_receipt.user_attached,
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
