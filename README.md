# FS Backend — Movie Cut Scenes API

FastAPI backend for storing and retrieving skipped scenes in **movies** and **web series episodes**, plus **AI-powered scene previews** (Gemini).

**Production:** https://fsbackend-production-8079.up.railway.app  
**API docs:** https://fsbackend-production-8079.up.railway.app/docs

---

## Features

- Movies with `title` + `release_year` (distinguishes remakes)
- Web series episodes (`series_title`, season, episode)
- Cut scenes with fixed reasons: `violence`, `inappropriate`, `eighteen_plus`
- Autocomplete movie suggestions
- Exists / create / read / update / delete
- AI preview (Gemini): estimated kissing / sexual content / nudity timelines

---

## Project structure

```
fs_backend/
├── main.py           # FastAPI app entry
├── config.py         # Env / DATABASE_URL / GEMINI_API_KEY
├── database.py       # SQLAlchemy engine + schema init
├── models.py         # Movie, Episode, CutScene tables
├── schemas.py        # Pydantic request/response models
├── routes.py         # API endpoints
├── ai_service.py     # Gemini AI scene preview
├── requirements.txt
├── railway.toml
├── .env.example
└── README.md
```

---

## Prerequisites

- Python **3.10+** recommended (3.12 works on Railway)
- PostgreSQL (local or Railway)
- Optional: [Gemini API key](https://aistudio.google.com/apikey) for AI preview

---

## Quick start (local)

### 1. Clone and enter the repo

```bash
git clone <your-repo-url>
cd fs_backend
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Local Postgres example
DATABASE_URL=postgresql://apple@localhost/movies_db

# Or Railway public URL
# DATABASE_URL=postgresql://postgres:PASSWORD@xxxx.proxy.rlwy.net:PORT/railway

# Required for AI preview endpoints
GEMINI_API_KEY=your_gemini_api_key_here
```

### 5. Create the database (local Postgres)

```bash
createdb movies_db
```

Tables are created automatically on app startup.

### 6. Run the server

```bash
# Local only (Mac / browser)
uvicorn main:app --reload

# Physical phone on same Wi‑Fi
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://127.0.0.1:8000  
- Interactive docs: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres connection string |
| `DATABASE_PUBLIC_URL` | No | Used if set (preferred for cross-project Railway) |
| `GEMINI_API_KEY` | For AI | Google AI Studio key for preview endpoints |
| `PORT` | Railway | Set automatically by Railway |

`config.py` converts `postgres://` / `postgresql://` to `postgresql+psycopg://` for SQLAlchemy.

---

## Main API overview

### Movies

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/movie/suggestions?query=` | Autocomplete by title |
| `GET` | `/api/movie/exists?title=&release_year=` | Check if movie exists |
| `POST` | `/api/movie` | Create movie + cut scenes |
| `GET` | `/api/movie/search?title=&release_year=` | Get by title + year |
| `GET` | `/api/movie/{movie_id}` | Get by ID |
| `PUT` | `/api/movie/{movie_id}` | Update movie + replace cut scenes |
| `DELETE` | `/api/movie/{movie_id}` | Delete movie |

### Episodes

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/episode/exists?series_title=&season_number=&episode_number=` | Check exists |
| `POST` | `/api/episode` | Create episode + cut scenes |
| `GET` | `/api/episode/search?...` | Get by series + season + episode |
| `GET` | `/api/episode/{episode_id}` | Get by ID |
| `PUT` | `/api/episode/{episode_id}` | Update episode + replace cut scenes |
| `DELETE` | `/api/episode/{episode_id}` | Delete episode |

### AI preview (movies)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/movie/{movie_id}/preview-scenes?title=&release_year=` | Always query Gemini |
| `GET` | `/api/movie/{movie_id}/preview-scenes?title=&release_year=` | DB first, else Gemini |

AI categories: `Kissing`, `Sexual Content`, `Nudity` only.

### Other

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/` | Health check |
| `GET` | `/api/skip-reasons` | Dropdown options for cut reasons |

Full interactive docs: `/docs`

---

## Example: create a movie

```bash
curl -X POST "http://127.0.0.1:8000/api/movie" \
  -H "Content-Type: application/json" \
  -d '{
    "movie_id": "inception_2010",
    "title": "Inception",
    "release_year": 2010,
    "duration": 8880,
    "cut_scenes": [
      { "start": 120.0, "end": 145.0, "reason": "violence" }
    ]
  }'
```

## Example: AI preview

```bash
curl -X POST "http://127.0.0.1:8000/api/movie/inception-2010/preview-scenes?title=Inception&release_year=2010"
```

---

## Deploy on Railway

1. Create a Railway project with **PostgreSQL** + this GitHub repo (same project preferred).
2. Set variables on the API service:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (variable reference), **or** public URL if DB is in another project
   - `GEMINI_API_KEY` = your Gemini key
3. Deploy. Start command is already in `railway.toml`:

```toml
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
```

4. Open the generated `*.up.railway.app` URL and `/docs`.

---

## Cut scene reasons (manual skip)

Frontend dropdown values (not free text):

| Value | Label |
|-------|-------|
| `violence` | Violence |
| `inappropriate` | Inappropriate |
| `eighteen_plus` | 18+ |

---

## Notes

- `POST` is **create-only** (returns `409` if already exists). Use `PUT` to edit.
- Check `GET /exists` before showing Play / Edit UI.
- AI times are **estimates** (`~20:30-23:45`), not exact seconds.
- Do not commit `.env` (it is gitignored).

---

## License

Private project — all rights reserved.
