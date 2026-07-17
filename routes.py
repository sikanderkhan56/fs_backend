import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from database import get_db
from models import CutScene, Episode, Movie
from schemas import (
    CreateSuccessResponse,
    CutSceneResponse,
    DeleteSuccessResponse,
    EpisodeResponse,
    EpisodeSchema,
    ExistsResponse,
    MovieResponse,
    MovieSchema,
    MovieSuggestionResponse,
    SELECTABLE_SKIP_REASONS,
    SkipReason,
    UpdateEpisodeSchema,
    UpdateMovieSchema,
    UpdateSuccessResponse,
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


def _scene_count(db: Session, content_type: str, reference_id: str) -> int:
    return (
        db.query(CutScene)
        .filter(
            CutScene.content_type == content_type,
            CutScene.reference_id == reference_id,
        )
        .count()
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


def _delete_content(db: Session, content_type: str, reference_id: str) -> None:
    db.query(CutScene).filter(
        CutScene.content_type == content_type,
        CutScene.reference_id == reference_id,
    ).delete()
    if content_type == "movie":
        db.query(Movie).filter(Movie.movie_id == reference_id).delete()
    else:
        db.query(Episode).filter(Episode.episode_id == reference_id).delete()
    db.commit()


SKIP_REASON_LABELS = {
    SkipReason.VIOLENCE: "Violence",
    SkipReason.INAPPROPRIATE: "Inappropriate",
    SkipReason.EIGHTEEN_PLUS: "18+",
    SkipReason.UNKNOWN: "Unknown (please re-select)",
}

_LEGACY_REASON_MAP = {
    "violence": SkipReason.VIOLENCE,
    "voilence": SkipReason.VIOLENCE,
    "inappropriate": SkipReason.INAPPROPRIATE,
    "eighteen_plus": SkipReason.EIGHTEEN_PLUS,
    "18_plus": SkipReason.EIGHTEEN_PLUS,
    "18+": SkipReason.EIGHTEEN_PLUS,
}


def _parse_stored_reason(raw: str) -> SkipReason:
    key = raw.strip().lower().replace(" ", "_")
    if key in _LEGACY_REASON_MAP:
        return _LEGACY_REASON_MAP[key]
    try:
        return SkipReason(key)
    except ValueError:
        return SkipReason.UNKNOWN


@router.get("/skip-reasons")
def list_skip_reasons():
    return [
        {"value": reason.value, "label": SKIP_REASON_LABELS[reason]}
        for reason in SELECTABLE_SKIP_REASONS
    ]


def _cut_scenes_to_response(scenes: List[CutScene]) -> List[CutSceneResponse]:
    return [
        CutSceneResponse(
            start=s.start_time,
            end=s.end_time,
            reason=_parse_stored_reason(s.reason),
        )
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
                reason=scene.reason.value,
            )
        )
    db.commit()


def _get_movie_scenes(db: Session, movie_id: str) -> List[CutScene]:
    return (
        db.query(CutScene)
        .filter(CutScene.content_type == "movie", CutScene.reference_id == movie_id)
        .all()
    )


def _get_episode_scenes(db: Session, episode_id: str) -> List[CutScene]:
    return (
        db.query(CutScene)
        .filter(
            CutScene.content_type == "episode",
            CutScene.reference_id == episode_id,
        )
        .all()
    )


def _movie_response(movie: Movie, scenes: List[CutScene]) -> MovieResponse:
    return MovieResponse(
        movie_id=movie.movie_id,
        title=movie.title,
        release_year=movie.release_year,
        duration=movie.duration,
        cut_scenes=_cut_scenes_to_response(scenes),
    )


def _episode_response(episode: Episode, scenes: List[CutScene]) -> EpisodeResponse:
    return EpisodeResponse(
        episode_id=episode.episode_id,
        series_title=episode.series_title,
        season_number=episode.season_number,
        episode_number=episode.episode_number,
        duration=episode.duration,
        cut_scenes=_cut_scenes_to_response(scenes),
    )


# --- Movie exists / create / read / update / delete ---


@router.get("/movie/exists", response_model=ExistsResponse)
def movie_exists(
    title: str = Query(..., min_length=1),
    release_year: int = Query(..., ge=1888, le=2100),
    db: Session = Depends(get_db),
):
    movie = _find_movie(db, title, release_year)
    if not movie:
        return ExistsResponse(exists=False)

    return ExistsResponse(
        exists=True,
        movie_id=movie.movie_id,
        title=movie.title,
        release_year=movie.release_year,
        scene_count=_scene_count(db, "movie", movie.movie_id),
    )


@router.get("/movie/suggestions", response_model=List[MovieSuggestionResponse])
def suggest_movies(
    query: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    normalized_query = _normalize_text(query).lower()
    if not normalized_query:
        return []

    scene_counts = (
        db.query(
            CutScene.reference_id.label("movie_id"),
            func.count(CutScene.id).label("scene_count"),
        )
        .filter(CutScene.content_type == "movie")
        .group_by(CutScene.reference_id)
        .subquery()
    )

    title = func.lower(Movie.title)
    rows = (
        db.query(
            Movie,
            func.coalesce(scene_counts.c.scene_count, 0).label("scene_count"),
        )
        .outerjoin(scene_counts, scene_counts.c.movie_id == Movie.movie_id)
        .filter(title.contains(normalized_query, autoescape=True))
        .order_by(
            case((title == normalized_query, 0), else_=1),
            case((title.startswith(normalized_query, autoescape=True), 0), else_=1),
            title.asc(),
            Movie.release_year.desc(),
        )
        .limit(limit)
        .all()
    )

    return [
        MovieSuggestionResponse(
            movie_id=movie.movie_id,
            title=movie.title,
            release_year=movie.release_year,
            scene_count=scene_count,
        )
        for movie, scene_count in rows
    ]


@router.post("/movie", response_model=CreateSuccessResponse, status_code=201)
def create_movie(movie: MovieSchema, db: Session = Depends(get_db)):
    title = _normalize_text(movie.title)

    if db.query(Movie).filter(Movie.movie_id == movie.movie_id).first():
        raise HTTPException(status_code=409, detail="Movie ID already exists")

    if _find_movie(db, title, movie.release_year):
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


@router.get("/movie/search", response_model=MovieResponse)
def search_movie(
    title: str = Query(..., min_length=1),
    release_year: int = Query(..., ge=1888, le=2100),
    db: Session = Depends(get_db),
):
    movie = _find_movie(db, title, release_year)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    return _movie_response(movie, _get_movie_scenes(db, movie.movie_id))


@router.get("/movie/{movie_id}", response_model=MovieResponse)
def get_movie_by_id(movie_id: str, db: Session = Depends(get_db)):
    movie = db.query(Movie).filter(Movie.movie_id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    return _movie_response(movie, _get_movie_scenes(db, movie_id))


@router.put("/movie/{movie_id}", response_model=UpdateSuccessResponse)
def update_movie(
    movie_id: str, movie: UpdateMovieSchema, db: Session = Depends(get_db)
):
    existing = db.query(Movie).filter(Movie.movie_id == movie_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Movie not found")

    title = _normalize_text(movie.title)
    duplicate = _find_movie(db, title, movie.release_year)
    if duplicate and duplicate.movie_id != movie_id:
        raise HTTPException(
            status_code=409,
            detail="Another movie with this title and release year already exists",
        )

    existing.title = title
    existing.release_year = movie.release_year
    existing.duration = movie.duration
    db.commit()

    _replace_cut_scenes(db, "movie", movie_id, movie.cut_scenes)

    return UpdateSuccessResponse(content_type="movie", id=movie_id)


@router.delete("/movie/{movie_id}", response_model=DeleteSuccessResponse)
def delete_movie(movie_id: str, db: Session = Depends(get_db)):
    movie = db.query(Movie).filter(Movie.movie_id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    _delete_content(db, "movie", movie_id)

    return DeleteSuccessResponse(content_type="movie", id=movie_id)


# --- Episode exists / create / read / update / delete ---


@router.get("/episode/exists", response_model=ExistsResponse)
def episode_exists(
    series_title: str = Query(..., min_length=1),
    season_number: int = Query(..., ge=1),
    episode_number: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    episode = _find_episode(db, series_title, season_number, episode_number)
    if not episode:
        return ExistsResponse(exists=False)

    return ExistsResponse(
        exists=True,
        episode_id=episode.episode_id,
        series_title=episode.series_title,
        season_number=episode.season_number,
        episode_number=episode.episode_number,
        scene_count=_scene_count(db, "episode", episode.episode_id),
    )


@router.post("/episode", response_model=CreateSuccessResponse, status_code=201)
def create_episode(episode: EpisodeSchema, db: Session = Depends(get_db)):
    series_title = _normalize_text(episode.series_title)

    if _find_episode(
        db, series_title, episode.season_number, episode.episode_number
    ):
        raise HTTPException(status_code=409, detail="Episode already exists")

    episode_id = episode.episode_id or _make_episode_id(
        series_title,
        episode.season_number,
        episode.episode_number,
    )

    if db.query(Episode).filter(Episode.episode_id == episode_id).first():
        raise HTTPException(status_code=409, detail="Episode ID already exists")

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

    return _episode_response(episode, _get_episode_scenes(db, episode.episode_id))


@router.get("/episode/{episode_id}", response_model=EpisodeResponse)
def get_episode_by_id(episode_id: str, db: Session = Depends(get_db)):
    episode = db.query(Episode).filter(Episode.episode_id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    return _episode_response(episode, _get_episode_scenes(db, episode_id))


@router.put("/episode/{episode_id}", response_model=UpdateSuccessResponse)
def update_episode(
    episode_id: str, episode: UpdateEpisodeSchema, db: Session = Depends(get_db)
):
    existing = db.query(Episode).filter(Episode.episode_id == episode_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Episode not found")

    series_title = _normalize_text(episode.series_title)
    duplicate = _find_episode(
        db, series_title, episode.season_number, episode.episode_number
    )
    if duplicate and duplicate.episode_id != episode_id:
        raise HTTPException(
            status_code=409,
            detail="Another episode with this series, season, and episode already exists",
        )

    existing.series_title = series_title
    existing.season_number = episode.season_number
    existing.episode_number = episode.episode_number
    existing.duration = episode.duration
    db.commit()

    _replace_cut_scenes(db, "episode", episode_id, episode.cut_scenes)

    return UpdateSuccessResponse(content_type="episode", id=episode_id)


@router.delete("/episode/{episode_id}", response_model=DeleteSuccessResponse)
def delete_episode(episode_id: str, db: Session = Depends(get_db)):
    episode = db.query(Episode).filter(Episode.episode_id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    _delete_content(db, "episode", episode_id)

    return DeleteSuccessResponse(content_type="episode", id=episode_id)
