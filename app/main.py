from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.normative import router as normative_router
from app.api.routes.web import router as web_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.security.middleware import RequestBodyLimitMiddleware, SecurityHeadersMiddleware

settings = get_settings()
configure_logging(settings.log_level)

docs_enabled = settings.enable_docs and settings.environment != "production"

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
)


app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts(),
)
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_bytes=settings.max_request_body_bytes,
)
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=settings.environment == "production",
)
register_exception_handlers(app)

app.include_router(health_router)
app.include_router(knowledge_router)
app.include_router(normative_router)
app.include_router(web_router)

WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount(
    "/static",
    StaticFiles(directory=str(WEB_DIR / "static")),
    name="static",
)
