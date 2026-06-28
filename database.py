import logging
from typing import Set

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from models import Base

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _column_names(inspector, table: str) -> Set[str]:
    if not inspector.has_table(table):
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def _needs_schema_reset(inspector) -> bool:
    cut_scene_cols = _column_names(inspector, "cut_scenes")
    movie_cols = _column_names(inspector, "movies")

    if cut_scene_cols and "content_type" not in cut_scene_cols:
        return True
    if movie_cols and "release_year" not in movie_cols:
        return True
    if not inspector.has_table("episodes"):
        return cut_scene_cols or movie_cols

    return False


def _reset_content_tables() -> None:
    logger.warning("Old database schema detected — recreating content tables")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS cut_scenes CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS episodes CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS movies CASCADE"))


def init_db():
    inspector = inspect(engine)
    if _needs_schema_reset(inspector):
        _reset_content_tables()
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
