import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
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


def _normalize_text(text: str) -> str:
    return text.strip()


def _find_episode(
    db: Session, series_title: str, season_number: int, episode_number: int
) -> Optional[Episode]:
    return (
        db.query(Episode)
        .filter(
            func.lower(Episode.series_title) == _normalize_text(series_title).lower(),
            Episode.season_number == season_number,
            Episode.episode_number == episode_number,
        )
        .first()
    )


def _find_movie(db: Session, title: str, release_year: int) -> Optional[Movie]:
    return (
        db.query(Movie)
        .filter(
            func.lower(Movie.title) == _normalize_text(title).lower(),
            Movie.release_year == release_year,
        )
        .first()
    )


def _replace_cut_scenes(
    db: Session, content_type: str, reference_id: str, cut_scenes: list
) -> None:
    db.query(CutScene).filter(
        CutScene.content_type == content_type,
        CutScene.reference_id == reference_id,
    ).delete()
    db.commit()
    _save_cut_scenes(db, content_type, reference_id, cut_scenes)


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
    title = _normalize_text(movie.title)
    existing = db.query(Movie).filter(Movie.movie_id == movie.movie_id).first()
    if existing:
        existing.title = title
        existing.release_year = movie.release_year
        existing.duration = movie.duration
        db.commit()
        _replace_cut_scenes(db, "movie", movie.movie_id, movie.cut_scenes)
        return CreateSuccessResponse(content_type="movie", id=movie.movie_id)

    by_title = _find_movie(db, title, movie.release_year)
    if by_title:
        raise HTTPException(
            status_code=409,
            detail="Movie with this title and release year already exists",
        )

    db_movie = Movie(
        movie_id=movie.movie_id,
        title=title,
        release_year=movie.release_year,
        duration=movie.duration,
    )
    db.add(db_movie)
    db.commit()

    _save_cut_scenes(db, "movie", movie.movie_id, movie.cut_scenes)

    return CreateSuccessResponse(content_type="movie", id=movie.movie_id)


@router.post("/episode", response_model=CreateSuccessResponse)
def create_episode(episode: EpisodeSchema, db: Session = Depends(get_db)):
    series_title = _normalize_text(episode.series_title)
    episode_id = episode.episode_id or _make_episode_id(
        series_title,
        episode.season_number,
        episode.episode_number,
    )

    existing = _find_episode(
        db, series_title, episode.season_number, episode.episode_number
    )
    if existing:
        existing.duration = episode.duration
        db.commit()
        _replace_cut_scenes(db, "episode", existing.episode_id, episode.cut_scenes)
        return CreateSuccessResponse(content_type="episode", id=existing.episode_id)

    db_episode = Episode(
        episode_id=episode_id,
        series_title=series_title,
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
    movie = _find_movie(db, title, release_year)
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
    episode = _find_episode(db, series_title, season_number, episode_number)
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
