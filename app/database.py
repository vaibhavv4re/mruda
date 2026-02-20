"""MRUDA — Database Engine & Session Factory."""

from sqlmodel import SQLModel, Session, create_engine
from app.config import settings

# Use check_same_thread=False only for SQLite
connect_args = {}
if settings.effective_database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.effective_database_url,
    echo=False,
    connect_args=connect_args,
)


def init_db() -> None:
    """Create all tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency — yields a DB session."""
    with Session(engine) as session:
        yield session
