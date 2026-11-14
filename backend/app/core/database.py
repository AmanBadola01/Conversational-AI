import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Base Model from which all database tables will inherit
Base = declarative_base()

def get_engine():
    """
    Creates the database engine.
    Connects to PostgreSQL using psycopg2.
    If PostgreSQL server is not running locally, provides an automatic SQLite fallback
    so development and testing are never blocked.
    """
    db_url = settings.DATABASE_URL
    try:
        # Normalize postgresql:// to postgresql+psycopg2:// for psycopg2 driver
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        if "postgresql" in db_url:
            # Create PostgreSQL engine with pool_pre_ping to verify connections
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 3}
            )
            # Verify the connection works
            with engine.connect() as conn:
                pass
            logger.info("Successfully connected to PostgreSQL database.")
            return engine
    except Exception as e:
        logger.warning(
            f"Could not connect to PostgreSQL at '{settings.DATABASE_URL}': {e}. "
            "Falling back to local SQLite database for uninterrupted development."
        )

    # Fallback to local SQLite if PostgreSQL is offline
    fallback_url = "sqlite:///./conversational_ai.db"
    return create_engine(
        fallback_url,
        connect_args={"check_same_thread": False}
    )

# Engine & Session Local factory
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    FastAPI dependency that yields a database session per request.
    Automatically closes the session when the request is completed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Creates all registered tables in the database if they do not exist.
    Also adds account-ownership columns to databases created before
    accounts existed, without touching their other data.
    """
    # Imports will be registered here when models are defined
    from backend.app.models import db_models  # noqa
    from sqlalchemy import inspect, text

    Base.metadata.create_all(bind=engine)
    additions = {
        "users": [("profile_number", "VARCHAR(80)")],
        "conversations": [("user_id", "VARCHAR(36)")],
        "entities": [("user_id", "VARCHAR(36)")],
        "personas": [("owner_id", "VARCHAR(36)")],
    }
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in additions.items():
            if table not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    logger.info("Added %s.%s for account ownership.", table, name)
    logger.info("Database tables initialized.")
