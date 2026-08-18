import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.utils.env import safe_load_dotenv

safe_load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./openmemory.db")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment")


def is_sqlite(url: str | None = None) -> bool:
    """Whether ``url`` uses the SQLite dialect."""
    return (url or DATABASE_URL).startswith("sqlite")


def is_postgresql(url: str | None = None) -> bool:
    """Whether ``url`` uses the PostgreSQL dialect."""
    return (url or DATABASE_URL).startswith("postgresql")


def engine_connect_args(url: str | None = None) -> dict:
    """SQLAlchemy ``connect_args`` appropriate for the dialect in ``url``.

    SQLite requires ``check_same_thread=False`` for multi-threaded access;
    PostgreSQL (via PgBouncer or direct) must not receive that argument.
    """
    if is_sqlite(url):
        return {"check_same_thread": False}
    return {}


def _pool_int(name: str, default: int) -> int:
    """Parse an integer pool env var, falling back to ``default`` on bad input.

    A mistyped value (empty, non-numeric) must not crash the API at import
    time — the pool is sized conservatively and the service keeps booting.
    """
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


engine = create_engine(
    DATABASE_URL,
    connect_args=engine_connect_args(),
    pool_size=_pool_int("DATABASE_POOL_SIZE", 10),
    max_overflow=_pool_int("DATABASE_MAX_OVERFLOW", 20),
    pool_timeout=_pool_int("DATABASE_POOL_TIMEOUT", 30),
    pool_recycle=_pool_int("DATABASE_POOL_RECYCLE", 1800),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Register Qdrant read-audit model with SQLAlchemy metadata (Alembic/tests).
import app.read_audit_log_model  # noqa: F401, E402


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
