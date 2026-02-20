"""MRUDA — Database Engine & Session Factory."""

from sqlmodel import SQLModel, Session, create_engine
from app.config import settings

db_url = settings.effective_database_url

# Build engine kwargs depending on backend
engine_kwargs: dict = {"echo": False}

if db_url.startswith("sqlite"):
    # SQLite-specific: allow multi-thread access
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL (Supabase) — serverless-friendly settings
    engine_kwargs["pool_pre_ping"] = True  # verify conn is alive before use
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_recycle"] = 300  # recycle stale connections

engine = create_engine(db_url, **engine_kwargs)


def init_db() -> None:
    """Create all tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency — yields a DB session."""
    with Session(engine) as session:
        yield session
