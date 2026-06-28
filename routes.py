import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import CutScene, Episode, Movie
from schemas import (
    CreateSuccessResponse,
    CutSceneResponse,
    EpisodeResponse,
    EpisodeSchema,
    MovieResponse,
    MovieSchema,
)

router = APIRouter(prefix="/api", tags=["content"])


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def _make_episode_id(series_title: str, season: int, episode: int) -> str:
    return f"{_slugify(series_title)}_s{season}_e{episode}"


def _cut_scenes_to_response(scenes: List[CutScene]) -> List[CutSceneResponse]:
    return [
        CutSceneResponse(start=s.start_time, end=s.end_time, reason=s.reason)
        for s in scenes
    ]


def _save_cut_scenes(
    db: Session,
    content_type: str,
    reference_id: str,
    cut_scenes: list,
) -> None:
    for scene in cut_scenes:
        db.add(
            CutScene(
                content_type=content_type,
                reference_id=reference_id,
                start_time=scene.start,
                end_time=scene.end,
                reason=scene.reason,
            )
        )
    db.commit()


@router.post("/movie", response_model=CreateSuccessResponse)
def create_movie(movie: MovieSchema, db: Session = Depends(get_db)):
    existing = db.query(Movie).filter(Movie.movie_id == movie.movie_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Movie ID already exists")

    db_movie = Movie(
        movie_id=movie.movie_id,
        title=movie.title,
        release_year=movie.release_year,
        duration=movie.duration,
    )
    db.add(db_movie)
    db.commit()

    _save_cut_scenes(db, "movie", movie.movie_id, movie.cut_scenes)

    return CreateSuccessResponse(content_type="movie", id=movie.movie_id)


@router.post("/episode", response_model=CreateSuccessResponse)
def create_episode(episode: EpisodeSchema, db: Session = Depends(get_db)):
    episode_id = episode.episode_id or _make_episode_id(
        episode.series_title,
        episode.season_number,
        episode.episode_number,
    )

    existing = db.query(Episode).filter(Episode.episode_id == episode_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Episode already exists")

    db_episode = Episode(
        episode_id=episode_id,
        series_title=episode.series_title,
        season_number=episode.season_number,
        episode_number=episode.episode_number,
        duration=episode.duration,
    )
    db.add(db_episode)
    db.commit()

    _save_cut_scenes(db, "episode", episode_id, episode.cut_scenes)

    return CreateSuccessResponse(content_type="episode", id=episode_id)


@router.get("/movie/search", response_model=MovieResponse)
def search_movie(
    title: str = Query(..., min_length=1),
    release_year: int = Query(..., ge=1888, le=2100),
    db: Session = Depends(get_db),
):
    movie = (
        db.query(Movie)
        .filter(Movie.title == title, Movie.release_year == release_year)
        .first()
    )
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    scenes = (
        db.query(CutScene)
        .filter(
            CutScene.content_type == "movie",
            CutScene.reference_id == movie.movie_id,
        )
        .all()
    )

    return MovieResponse(
        movie_id=movie.movie_id,
        title=movie.title,
        release_year=movie.release_year,
        duration=movie.duration,
        cut_scenes=_cut_scenes_to_response(scenes),
    )


@router.get("/movie/{movie_id}", response_model=MovieResponse)
def get_movie_by_id(movie_id: str, db: Session = Depends(get_db)):
    movie = db.query(Movie).filter(Movie.movie_id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    scenes = (
        db.query(CutScene)
        .filter(CutScene.content_type == "movie", CutScene.reference_id == movie_id)
        .all()
    )

    return MovieResponse(
        movie_id=movie.movie_id,
        title=movie.title,
        release_year=movie.release_year,
        duration=movie.duration,
        cut_scenes=_cut_scenes_to_response(scenes),
    )


@router.get("/episode/search", response_model=EpisodeResponse)
def search_episode(
    series_title: str = Query(..., min_length=1),
    season_number: int = Query(..., ge=1),
    episode_number: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    episode = (
        db.query(Episode)
        .filter(
            Episode.series_title == series_title,
            Episode.season_number == season_number,
            Episode.episode_number == episode_number,
        )
        .first()
    )
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    scenes = (
        db.query(CutScene)
        .filter(
            CutScene.content_type == "episode",
            CutScene.reference_id == episode.episode_id,
        )
        .all()
    )

    return _episode_response(episode, scenes)


@router.get("/episode/{episode_id}", response_model=EpisodeResponse)
def get_episode_by_id(episode_id: str, db: Session = Depends(get_db)):
    episode = db.query(Episode).filter(Episode.episode_id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    scenes = (
        db.query(CutScene)
        .filter(
            CutScene.content_type == "episode",
            CutScene.reference_id == episode_id,
        )
        .all()
    )

    return _episode_response(episode, scenes)


def _episode_response(episode: Episode, scenes: List[CutScene]) -> EpisodeResponse:
    return EpisodeResponse(
        episode_id=episode.episode_id,
        series_title=episode.series_title,
        season_number=episode.season_number,
        episode_number=episode.episode_number,
        duration=episode.duration,
        cut_scenes=_cut_scenes_to_response(scenes),
    )
