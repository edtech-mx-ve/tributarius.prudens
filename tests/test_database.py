from sqlalchemy import text

from app.core.database import database_session


def test_database_connection() -> None:
    with database_session() as session:
        value = session.execute(text("SELECT 1")).scalar_one()
    assert value == 1
