from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CutSceneSchema(BaseModel):
    start: float
    end: float
    reason: str


class MovieSchema(BaseModel):
    movie_id: str
    title: str
    release_year: int = Field(..., ge=1888, le=2100)
    duration: float
    cut_scenes: List[CutSceneSchema]


class EpisodeSchema(BaseModel):
    series_title: str
    season_number: int = Field(..., ge=1)
    episode_number: int = Field(..., ge=1)
    duration: float
    cut_scenes: List[CutSceneSchema]
    episode_id: Optional[str] = None


class CutSceneResponse(BaseModel):
    start: float
    end: float
    reason: str


class MovieResponse(BaseModel):
    movie_id: str
    title: str
    release_year: int
    duration: float
    cut_scenes: List[CutSceneResponse]


class EpisodeResponse(BaseModel):
    episode_id: str
    series_title: str
    season_number: int
    episode_number: int
    duration: float
    cut_scenes: List[CutSceneResponse]


class CreateSuccessResponse(BaseModel):
    status: Literal["success"] = "success"
    content_type: Literal["movie", "episode"]
    id: str
