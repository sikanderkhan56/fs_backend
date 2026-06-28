from typing import List

from pydantic import BaseModel


class CutSceneSchema(BaseModel):
    start: float
    end: float
    reason: str


class MovieSchema(BaseModel):
    movie_id: str
    title: str
    duration: float
    cut_scenes: List[CutSceneSchema]
