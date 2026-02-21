"""MRUDA — Database Engine & Session Factory."""

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text
from app.config import settings
from app.core.logging import get_logger

logger = get_logger("database")

db_url = settings.effective_database_url


def _mask_url(url: str) -> str:
    """Mask password in DB URL for safe logging."""
    if "@" in url:
        # postgresql://user:PASSWORD@host:port/db
        before_at = url.split("@")[0]
        after_at = url.split("@", 1)[1]
        if ":" in before_at.split("//", 1)[-1]:
            scheme_user = before_at.rsplit(":", 1)[0]
            return f"{scheme_user}:****@{after_at}"
    return url


# ── Log what we're connecting to ──
if db_url.startswith("sqlite"):
    logger.info(f"📦 Database backend: SQLite")
    logger.info(f"📍 Database path: {db_url}")
else:
    logger.info(f"🐘 Database backend: PostgreSQL")
    logger.info(f"📍 Database URL: {_mask_url(db_url)}")

# ── Build engine kwargs ──
engine_kwargs: dict = {"echo": False}

if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(db_url, **engine_kwargs)
logger.info("⚙️  Database engine created")


def test_connection() -> bool:
    """Test the database connection with SELECT 1."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        logger.info("✅ Database connection test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection test: FAILED — {e}")
        return False


def init_db() -> None:
    """Create all tables."""
    logger.info("🔨 Creating database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("✅ Database tables ready")


def get_session():
    """Dependency — yields a DB session."""
    with Session(engine) as session:
        yield session
