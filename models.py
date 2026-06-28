from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Movie(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True)
    movie_id = Column(String, unique=True)
    title = Column(String)
    duration = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class CutScene(Base):
    __tablename__ = "cut_scenes"

    id = Column(Integer, primary_key=True)
    movie_id = Column(String)
    start_time = Column(Float)
    end_time = Column(Float)
    reason = Column(String)
