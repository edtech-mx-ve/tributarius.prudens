from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base declarativa de modelos SQLAlchemy."""


def _connect_args(database_url: str) -> dict[str, object]:
    """Devuelve argumentos específicos sin acoplar el dominio a SQLite."""
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=_connect_args(settings.database_url),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def database_session() -> Generator[Session, None, None]:
    """Abre una sesión transaccional con rollback seguro ante error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI con cierre seguro de la sesión."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
