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


private_url = _clean_url(os.getenv("DATABASE_URL"))
public_url = _clean_url(os.getenv("DATABASE_PUBLIC_URL"))

# Public URL works across Railway projects; internal (*.railway.internal) does not.
if public_url:
    DATABASE_URL = public_url
elif private_url and "railway.internal" not in private_url:
    DATABASE_URL = private_url
elif private_url:
    raise RuntimeError(
        "DATABASE_URL uses postgres.railway.internal, which only works when "
        "Postgres and this app are in the SAME Railway project. "
        "You have two projects — in the backend service Variables, delete "
        "DATABASE_URL and set DATABASE_PUBLIC_URL to your Postgres public URL "
        "(Postgres service → Connect → Public URL), or merge both into one project."
    )
else:
    DATABASE_URL = "postgresql+psycopg://apple@localhost/movies_db"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

_parsed = urlparse(DATABASE_URL)
logger.info("Database host: %s:%s", _parsed.hostname, _parsed.port or 5432)
