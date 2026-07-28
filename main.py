import logging
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(1, 6):
        try:
            init_db()
            break
        except Exception as exc:
            if attempt == 5:
                raise
            logger.warning(
                "Database not ready (attempt %s/5): %s", attempt, exc
            )
            time.sleep(2 ** attempt)
    yield


app = FastAPI(title="Movie Cut Scenes API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def read_root():
    return {"message": "Movie Backend API"}
