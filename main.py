from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routes import router

app = FastAPI(title="Movie Cut Scenes API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(router)


@app.get("/")
def read_root():
    return {"message": "Movie Backend API"}
