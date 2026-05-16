from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from .models import Base
import logging

logger = logging.getLogger(__name__)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine(db_url: str, echo: bool = False):
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=echo,
    )
    Base.metadata.create_all(bind=engine)
    _migrate(engine)
    logger.info(f"Database initialised: {db_url}")
    return engine


def _migrate(engine):
    """Non-destructive migrations for existing databases."""
    migrations = [
        "ALTER TABLE expenses ADD COLUMN transaction_type VARCHAR(10) DEFAULT 'expense' NOT NULL",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                logger.info(f"Migration applied: {sql[:60]}")
            except Exception:
                pass  # column already exists


def get_session_factory(engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db(session_factory: sessionmaker):
    db: Session = session_factory()
    try:
        yield db
    finally:
        db.close()
