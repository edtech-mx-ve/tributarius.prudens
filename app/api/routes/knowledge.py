from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import database_session
from app.domain.knowledge import MasterMatrixEntryRead
from app.services.knowledge_matrix import list_matrix

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/matrix", response_model=list[MasterMatrixEntryRead])
def get_master_matrix() -> list[MasterMatrixEntryRead]:
    try:
        with database_session() as session:
            return list_matrix(session)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="No fue posible consultar la matriz de conocimiento.",
        ) from exc
