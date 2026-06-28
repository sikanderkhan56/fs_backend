from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (UniqueConstraint("title", "release_year", name="uq_movie_title_year"),)

    id = Column(Integer, primary_key=True)
    movie_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    release_year = Column(Integer, nullable=False)
    duration = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint(
            "series_title",
            "season_number",
            "episode_number",
            name="uq_episode_series_season_ep",
        ),
    )

    id = Column(Integer, primary_key=True)
    episode_id = Column(String, unique=True, nullable=False)
    series_title = Column(String, nullable=False)
    season_number = Column(Integer, nullable=False)
    episode_number = Column(Integer, nullable=False)
    duration = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CutScene(Base):
    __tablename__ = "cut_scenes"

    id = Column(Integer, primary_key=True)
    content_type = Column(String, nullable=False)  # "movie" or "episode"
    reference_id = Column(String, nullable=False, index=True)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    reason = Column(String, nullable=False)
