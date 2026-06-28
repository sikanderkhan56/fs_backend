from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import CutScene, Movie
from schemas import MovieSchema

router = APIRouter(prefix="/api", tags=["movies"])


@router.get("/movie/{movie_id}")
def get_movie_cut_scenes(movie_id: str, db: Session = Depends(get_db)):
    scenes = db.query(CutScene).filter(CutScene.movie_id == movie_id).all()

    if not scenes:
        raise HTTPException(status_code=404, detail="Movie not found")

    return {
        "movie_id": movie_id,
        "cut_scenes": [
            {"start": s.start_time, "end": s.end_time, "reason": s.reason}
            for s in scenes
        ],
    }


@router.post("/movie")
def create_movie(movie: MovieSchema, db: Session = Depends(get_db)):
    db_movie = Movie(
        movie_id=movie.movie_id,
        title=movie.title,
        duration=movie.duration,
    )
    db.add(db_movie)
    db.commit()

    for scene in movie.cut_scenes:
        db_scene = CutScene(
            movie_id=movie.movie_id,
            start_time=scene.start,
            end_time=scene.end,
            reason=scene.reason,
        )
        db.add(db_scene)
    db.commit()

    return {"status": "success", "movie_id": movie.movie_id}
