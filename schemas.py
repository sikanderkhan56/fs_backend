from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SkipReason(str, Enum):
    VIOLENCE = "violence"
    INAPPROPRIATE = "inappropriate"
    EIGHTEEN_PLUS = "eighteen_plus"
    UNKNOWN = "unknown"  # legacy free-text data only; not valid on create/update


SELECTABLE_SKIP_REASONS = (
    SkipReason.VIOLENCE,
    SkipReason.INAPPROPRIATE,
    SkipReason.EIGHTEEN_PLUS,
)


class CutSceneSchema(BaseModel):
    start: float
    end: float
    reason: SkipReason


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
    reason: SkipReason


class MovieResponse(BaseModel):
    movie_id: str
    title: str
    release_year: int
    duration: float
    cut_scenes: List[CutSceneResponse]


class MovieSuggestionResponse(BaseModel):
    movie_id: str
    title: str
    release_year: int
    scene_count: int


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


class UpdateSuccessResponse(BaseModel):
    status: Literal["success"] = "success"
    content_type: Literal["movie", "episode"]
    id: str


class DeleteSuccessResponse(BaseModel):
    status: Literal["success"] = "success"
    content_type: Literal["movie", "episode"]
    id: str


class ExistsResponse(BaseModel):
    exists: bool
    movie_id: Optional[str] = None
    title: Optional[str] = None
    release_year: Optional[int] = None
    episode_id: Optional[str] = None
    series_title: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    scene_count: int = 0


class UpdateMovieSchema(BaseModel):
    title: str
    release_year: int = Field(..., ge=1888, le=2100)
    duration: float
    cut_scenes: List[CutSceneSchema]


class UpdateEpisodeSchema(BaseModel):
    series_title: str
    season_number: int = Field(..., ge=1)
    episode_number: int = Field(..., ge=1)
    duration: float
    cut_scenes: List[CutSceneSchema]
