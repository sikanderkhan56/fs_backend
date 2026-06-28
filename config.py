import logging
import os
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _clean_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return url.strip().strip('"').strip("'")


DATABASE_URL = _clean_url(os.getenv("DATABASE_URL")) or _clean_url(
    os.getenv("DATABASE_PUBLIC_URL")
)

if not DATABASE_URL:
    DATABASE_URL = "postgresql+psycopg://apple@localhost/movies_db"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

_parsed = urlparse(DATABASE_URL)
logger.info("Database host: %s:%s", _parsed.hostname, _parsed.port or 5432)