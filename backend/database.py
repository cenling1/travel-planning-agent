from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from . import models

    if settings.is_postgres:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    if settings.database_url.startswith("sqlite"):
        _ensure_sqlite_schema()


def _ensure_sqlite_schema() -> None:
    with engine.begin() as connection:
        document_columns = {
            row[1] for row in connection.execute(text("PRAGMA table_info(knowledge_documents)"))
        }
        if "owner_id" not in document_columns:
            connection.execute(
                text(
                    "ALTER TABLE knowledge_documents "
                    "ADD COLUMN owner_id VARCHAR(64) NOT NULL DEFAULT 'local'"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_owner_id "
                    "ON knowledge_documents (owner_id)"
                )
            )


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
