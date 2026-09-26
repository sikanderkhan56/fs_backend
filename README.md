# FS Backend — Movie Cut Scenes API

A **FastAPI** backend that powers a mobile app for skipping inappropriate scenes in **movies** and **web series episodes**. It stores exact cut timestamps in **PostgreSQL** and can suggest estimated scenes using **Google Gemini AI** when no saved data exists.

**Production:** https://fsbackend-production-8079.up.railway.app  
**Interactive API docs:** https://fsbackend-production-8079.up.railway.app/docs

> **New here?** Follow [`GETTING_STARTED.md`](./GETTING_STARTED.md) for installation and local setup.

---

## What this project is

This is the **server-side API** for a content-filtering video experience. Users (via a React Native app) can:

1. Select a movie or web series episode  
2. See if cut-scene data already exists  
3. Get **AI estimates** for kissing / sexual content / nudity scenes  
4. Save, play with, edit, or delete exact skip segments  

The backend is the source of truth for skip data and AI previews.

---

## What problem it solves

Watching movies or series often includes scenes some viewers want to skip (kissing, nudity, sexual content). Doing that well requires:

| Challenge | How this project handles it |
|-----------|----------------------------|
| Same title, different remakes | Movies identified by **title + release year** |
| Web series structure | Episodes identified by **series + season + episode** |
| Shared / reusable skip data | Stored in PostgreSQL and fetched by ID or search |
| No data yet for a title | Gemini AI returns **estimated** timelines as a starting point |
| Consistent skip reasons | Fixed enums — no free-text reasons on create/update |

---

## What it does

### Core product behavior

- **Create** movies or episodes with a list of cut scenes (`start`, `end`, `reason`)
- **Search / load** existing cut scenes for playback
- **Check existence** so the app can show “Play” or “Edit”
- **Update** cut scenes (full replace) or **delete** a title
- **Autocomplete** movie titles as the user types
- **AI preview** of estimated kissing / sex / nudity scenes when DB has nothing

### Manual cut-scene reasons (saved in DB)

| Value | Meaning |
|-------|---------|
| `violence` | Violence |
| `inappropriate` | Inappropriate |
| `eighteen_plus` | 18+ / adult content |

### AI preview categories (estimates only)

| Category | Meaning |
|----------|---------|
| `Kissing` | Mouth-to-mouth / French kiss |
| `Sexual Content` | Intercourse or clear sexual activity |
| `Nudity` | Naked body or private parts shown |

AI times use approximate ranges like `~01:12:00-01:14:30`. They are **not** exact frame times — the app should confirm with frame-by-frame preview before saving.

---

## Tech stack

| Area | Choice |
|------|--------|
| Language | Python |
| API framework | FastAPI |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2.x |
| Database | PostgreSQL |
| Driver | psycopg 3 |
| AI | Google Gemini (`gemini-flash-lite-latest`, fallback `gemini-flash-latest`) |
| Config | python-dotenv |
| Server | Uvicorn |
| Hosting | Railway |

---

## Architecture

```
React Native app
       │
       ▼
 FastAPI (routes + Pydantic schemas)
       │
  ┌────┴────┐
  ▼         ▼
PostgreSQL   Gemini AI service
(exact cuts) (estimated scenes)
```

### Code layout

| File | Role |
|------|------|
| `main.py` | App entry, CORS, lifespan / DB init |
| `config.py` | Env loading, `DATABASE_URL`, `GEMINI_API_KEY` |
| `database.py` | Engine, sessions, schema create / migrate |
| `models.py` | SQLAlchemy tables: `Movie`, `Episode`, `CutScene` |
| `schemas.py` | Request/response contracts and enums |
| `routes.py` | All HTTP endpoints under `/api` |
| `ai_service.py` | Gemini prompt + call + JSON parse + retries |
| `railway.toml` | Production start command |
| `.env.example` | Documented env vars (no secrets) |

### Design approach

- **Layered API:** HTTP routes → schemas → models / AI service  
- **Create vs edit:** `POST` creates only (`409` if duplicate); `PUT` replaces cut scenes  
- **Exists-first UX:** clients call `/exists` before Play / Edit  
- **Shared cut table:** `cut_scenes` serves both movies and episodes via `content_type` + `reference_id`  
- **Strict validation:** skip reasons are enums; invalid values return `422`  
- **AI as fallback:** prefer DB exact data; call Gemini only when needed  
- **Resilient AI calls:** SSL via certifi, retries, model fallback on overload  

---

## Database

### `movies`

| Column | Notes |
|--------|--------|
| `movie_id` | Unique string ID (e.g. `inception_2010`) |
| `title` | Display title |
| `release_year` | Distinguishes remakes |
| `duration` | Total length in seconds |
| `created_at` | Timestamp |

**Unique:** `(title, release_year)`

### `episodes`

| Column | Notes |
|--------|--------|
| `episode_id` | Unique ID (auto-generated slug if omitted) |
| `series_title` | Show name |
| `season_number` | ≥ 1 |
| `episode_number` | ≥ 1 |
| `duration` | Episode length in seconds |
| `created_at` | Timestamp |

**Unique:** `(series_title, season_number, episode_number)`  
**Example ID:** `breaking_bad_s1_e3`

### `cut_scenes`

| Column | Notes |
|--------|--------|
| `content_type` | `movie` or `episode` |
| `reference_id` | `movie_id` or `episode_id` |
| `start_time` / `end_time` | Seconds |
| `reason` | Enum string |

Indexed on `reference_id` for fast lookups.

---

## API surface

Base path: `/api`

### Movies

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/movie/suggestions` | Title autocomplete |
| `GET` | `/movie/exists` | Exists + scene count |
| `POST` | `/movie` | Create movie + cut scenes |
| `GET` | `/movie/search` | Get by title + year |
| `GET` | `/movie/{movie_id}` | Get by ID |
| `PUT` | `/movie/{movie_id}` | Update + replace cut scenes |
| `DELETE` | `/movie/{movie_id}` | Delete movie + scenes |

### Episodes

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/episode/exists` | Exists + scene count |
| `POST` | `/episode` | Create episode + cut scenes |
| `GET` | `/episode/search` | Get by series / season / episode |
| `GET` | `/episode/{episode_id}` | Get by ID |
| `PUT` | `/episode/{episode_id}` | Update + replace cut scenes |
| `DELETE` | `/episode/{episode_id}` | Delete episode + scenes |

### AI scene preview (movies)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/movie/{movie_id}/preview-scenes` | Always query Gemini |
| `GET` | `/movie/{movie_id}/preview-scenes` | Prefer DB; else Gemini |

Both take query params: `title`, `release_year`.

### Other

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Health check |
| `GET` | `/api/skip-reasons` | Labels for manual reason dropdown |
| `GET` | `/docs` | Swagger UI |

---

## Typical client flows

### New movie — save cuts

1. User enters title + year (+ optional AI preview)  
2. `POST /api/movie` with `cut_scenes`  
3. App stores returned `id` / plays with exact seconds  

### Existing movie — play or edit

1. `GET /api/movie/exists?title=&release_year=`  
2. If `exists: true` → offer Play or Edit  
3. Play: `GET /api/movie/{movie_id}` or `/movie/search`  
4. Edit: load scenes → user changes list → `PUT /api/movie/{movie_id}`  

### No DB data — AI assist

1. `GET` or `POST` `.../preview-scenes`  
2. Show estimated scenes (`source: "ai_preview"`)  
3. User confirms timings → save via `POST` / `PUT` with enum reasons  

### Web series episode

Same pattern as movies, using `/api/episode/*` and series / season / episode fields.

---

## AI service behavior

- Prompt is constrained to **Kissing**, **Sexual Content**, and **Nudity** only  
- Explicitly ignores violence, guns, fighting, cheek kisses, etc.  
- Responses are JSON-only; times are approximate (`~`)  
- Generation uses low/zero temperature for more stable suggestions  
- On failure: retries, then falls back to another Gemini model when possible  

---

## Environment (overview)

| Variable | Used for |
|----------|----------|
| `DATABASE_URL` | PostgreSQL connection |
| `DATABASE_PUBLIC_URL` | Optional public Railway URL override |
| `GEMINI_API_KEY` | AI preview endpoints |
| `PORT` | Bound automatically on Railway |

Secrets belong in `.env` / Railway Variables — never commit real keys.

---

## Deployment

Deployed on **Railway** with PostgreSQL. The API listens on `0.0.0.0:$PORT` (see `railway.toml`). For physical devices during local development, the server must bind to `0.0.0.0` and the app uses the Mac’s LAN IP.

---

## Related docs

| Doc | Status |
|-----|--------|
| `README.md` | Project overview (what / why / how it works) |
| `PRD.md` | Product requirements for developers |
| `ARCHITECTURE.md` | Full system design, data models, tech stack |
| `ARCHITECTURE-ESSENTIALS.md` | Critical decisions only (quick reference) |
| `AGENTS.md` | Instructions for AI agents working in this repo |
| `GETTING_STARTED.md` | Installation, env setup, run locally / Railway |

---

## License

Private project — all rights reserved.
