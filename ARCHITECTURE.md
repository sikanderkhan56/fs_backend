# Architecture

**Project:** FS Backend — Movie Cut Scenes API  
**Audience:** Backend and full-stack developers  
**Related:** `README.md` (overview), `PRD.md` (product requirements), `ARCHITECTURE-ESSENTIALS.md` (quick reference)

This document describes system architecture, tech stack, data models, request flow, AI integration, deployment topology, and design decisions.

> Need only the outline? See [`ARCHITECTURE-ESSENTIALS.md`](./ARCHITECTURE-ESSENTIALS.md).

---

## 1. System context

```
┌──────────────────────────────────────────────────────────┐
│                     External actors                      │
│  React Native app (physical device / emulator)           │
└────────────────────────────┬─────────────────────────────┘
                             │ HTTP / HTTPS
                             ▼
┌──────────────────────────────────────────────────────────┐
│                 FS Backend (this service)                │
│  FastAPI + Uvicorn                                       │
│  Routes · Pydantic schemas · SQLAlchemy · AI service     │
└───────────────┬────────────────────────────┬─────────────┘
                │                            │
                ▼                            ▼
     ┌──────────────────┐        ┌──────────────────────┐
     │   PostgreSQL     │        │  Google Gemini API   │
     │   Exact cuts     │        │  Estimated previews  │
     └──────────────────┘        └──────────────────────┘
```

**Responsibility of this service**

- Own skip-scene data for movies and episodes  
- Validate and persist CRUD operations  
- Optionally call Gemini for estimated kissing / sex / nudity scenes  
- Expose OpenAPI at `/docs`  

**Not this service’s responsibility**

- Video decoding / playback  
- User authentication (not implemented yet)  
- Frame-accurate AI timestamps  

---

## 2. Tech stack

| Layer | Technology | Role |
|-------|------------|------|
| Language | Python 3.10+ (3.12 on Railway) | Runtime |
| Web framework | FastAPI `0.104.x` | REST API, DI, OpenAPI |
| ASGI server | Uvicorn | Process / HTTP server |
| Validation | Pydantic v2 | Request/response contracts, enums |
| ORM | SQLAlchemy 2.x | Models + sessions |
| Database | PostgreSQL | Persistent storage |
| DB driver | psycopg 3 (`psycopg[binary]`) | Postgres protocol |
| Config | python-dotenv | Local env loading |
| SSL (AI calls) | certifi | Trusted CA bundle for Gemini HTTPS |
| AI provider | Google Gemini REST API | Scene preview estimates |
| Deploy | Railway + Nixpacks | Build & host |
| Client (external) | React Native | Consumer of this API |

### Key dependencies (`requirements.txt`)

- `fastapi`, `uvicorn`
- `sqlalchemy`, `psycopg[binary]`
- `pydantic`, `python-dotenv`, `certifi`

---

## 3. High-level architecture style

The backend follows a **simple layered monolith**:

```
┌─────────────────────────────────────┐
│ Presentation: FastAPI routes        │  routes.py, main.py
├─────────────────────────────────────┤
│ Application contracts: Pydantic     │  schemas.py
├─────────────────────────────────────┤
│ Domain / services                   │  ai_service.py (+ route helpers)
├─────────────────────────────────────┤
│ Persistence: SQLAlchemy models      │  models.py, database.py
├─────────────────────────────────────┤
│ Infrastructure: config / env        │  config.py
└─────────────────────────────────────┘
```

### Why this shape

- Small team / single deployable service  
- Clear file boundaries without over-engineering microservices  
- FastAPI + SQLAlchemy is a conventional Python API stack  
- AI is isolated in `ai_service.py` so CRUD stays usable if Gemini is down  

---

## 4. Component diagram

```
main.py
  ├── load_dotenv()
  ├── lifespan → database.init_db() (with retries)
  ├── CORSMiddleware
  └── include_router(routes.router)

routes.py  (/api/*)
  ├── Movie CRUD / search / exists / suggestions
  ├── Episode CRUD / search / exists
  ├── Preview scenes (DB or AI)
  └── skip-reasons

ai_service.py
  └── MovieAIService.get_scene_preview()
        └── Gemini generateContent (multi-model + retries)

database.py
  ├── engine (pool_pre_ping)
  ├── SessionLocal / get_db()
  └── init_db() (+ legacy schema reset)

models.py
  ├── Movie
  ├── Episode
  └── CutScene

schemas.py
  └── Request/response DTOs + SkipReason enum

config.py
  └── DATABASE_URL resolution + GEMINI_API_KEY
```

---

## 5. Request lifecycle

### 5.1 Typical CRUD request

```
Client
  → Uvicorn / FastAPI
  → Route handler
  → Pydantic validation (422 if invalid)
  → Depends(get_db) → SQLAlchemy Session
  → Query / insert / update / delete
  → commit
  → JSON response
  → session closed in get_db finally
```

### 5.2 AI preview request

```
Client → POST/GET .../preview-scenes
  → If GET and movie found in DB:
       return source=database + cut_scenes
  → Else:
       MovieAIService.get_scene_preview(title, year)
         → build constrained prompt
         → call Gemini (lite model, then fallback)
         → parse JSON
         → return source=ai_preview + estimated_scenes
  → On AI failure: HTTP 503 with detail
```

### 5.3 Startup

```
Process start
  → load_dotenv / config
  → lifespan:
       retry init_db up to 5 times (DB may boot slower than app)
  → create_all tables (optionally drop/recreate if legacy schema detected)
  → serve traffic
```

---

## 6. Data architecture

### 6.1 Entity relationship (logical)

```
┌────────────────┐       ┌─────────────────────┐
│    movies      │       │      episodes       │
│────────────────│       │─────────────────────│
│ id (PK)        │       │ id (PK)             │
│ movie_id (UQ)  │       │ episode_id (UQ)     │
│ title          │       │ series_title        │
│ release_year   │       │ season_number       │
│ duration       │       │ episode_number      │
│ created_at     │       │ duration            │
└───────┬────────┘       │ created_at          │
        │                └──────────┬──────────┘
        │                           │
        │     content_type +        │
        │     reference_id          │
        ▼                           ▼
┌──────────────────────────────────────────────┐
│                 cut_scenes                   │
│──────────────────────────────────────────────│
│ id (PK)                                      │
│ content_type   ("movie" | "episode")         │
│ reference_id   (movie_id | episode_id, IDX)  │
│ start_time / end_time (seconds)              │
│ reason (enum string)                         │
└──────────────────────────────────────────────┘
```

There is **no SQL FK** from `cut_scenes` to movies/episodes today. Association is logical via `content_type` + `reference_id`. Deletes are handled in application code (`_delete_content`).

### 6.2 Table: `movies`

| Column | Type | Constraints / notes |
|--------|------|---------------------|
| `id` | Integer | PK, surrogate |
| `movie_id` | String | Unique business ID (client-provided) |
| `title` | String | Required |
| `release_year` | Integer | Required; remake discriminator |
| `duration` | Float | Seconds |
| `created_at` | DateTime | Default UTC now |

**Unique constraint:** `(title, release_year)` → `uq_movie_title_year`

### 6.3 Table: `episodes`

| Column | Type | Constraints / notes |
|--------|------|---------------------|
| `id` | Integer | PK |
| `episode_id` | String | Unique; auto-slug if omitted (`series_s{N}_e{M}`) |
| `series_title` | String | Required |
| `season_number` | Integer | ≥ 1 |
| `episode_number` | Integer | ≥ 1 |
| `duration` | Float | Seconds |
| `created_at` | DateTime | Default UTC now |

**Unique constraint:** `(series_title, season_number, episode_number)`

### 6.4 Table: `cut_scenes`

| Column | Type | Constraints / notes |
|--------|------|---------------------|
| `id` | Integer | PK |
| `content_type` | String | `movie` or `episode` |
| `reference_id` | String | Indexed; points to movie_id/episode_id |
| `start_time` | Float | Seconds |
| `end_time` | Float | Seconds |
| `reason` | String | Validated by Pydantic enum on write |

### 6.5 Domain enums

**Persisted skip reasons (manual cuts)**

| Value | Use |
|-------|-----|
| `violence` | Violence |
| `inappropriate` | Inappropriate |
| `eighteen_plus` | 18+ content |
| `unknown` | Legacy read compatibility only |

**AI preview categories (not persisted as-is)**

| Value | Use |
|-------|-----|
| `Kissing` | Mouth-to-mouth / French kiss |
| `Sexual Content` | Intercourse / clear sexual activity |
| `Nudity` | Naked body / private parts |

Client must map AI categories → skip reasons before `POST`/`PUT`.

### 6.6 Schema init / migration strategy

`database.init_db()`:

1. Inspect existing tables/columns  
2. If legacy shape detected (e.g. missing `content_type` or `release_year`), drop content tables  
3. `Base.metadata.create_all()`  

**Tradeoff:** simple for early development; destructive on schema reset. Future: Alembic migrations.

---

## 7. API architecture

### 7.1 Routing

- Router prefix: `/api`  
- Tags: `content`  
- App root health: `GET /`  

### 7.2 Endpoint groups

| Group | Paths | Pattern |
|-------|-------|---------|
| Movies | `/api/movie/*` | REST + search/exists/suggestions |
| Episodes | `/api/episode/*` | REST + search/exists |
| AI preview | `/api/movie/{id}/preview-scenes` | GET (DB→AI) / POST (AI only) |
| Meta | `/api/skip-reasons` | Static enum labels |

### 7.3 Command semantics

| Verb | Semantics in this project |
|------|---------------------------|
| `POST` | Create only → `201` or `409` |
| `PUT` | Replace metadata + **full** cut scene list |
| `GET` | Read / search / exists / suggestions / preview |
| `DELETE` | Remove parent + related cut scenes |

### 7.4 Validation boundary

All write payloads go through Pydantic schemas (`schemas.py`). Invalid enums/types → FastAPI `422` with field details.

### 7.5 CORS

Currently permissive (`allow_origins=["*"]`) for mobile development. Tighten for production hardening if needed.

---

## 8. AI architecture

### 8.1 Component

`MovieAIService` in `ai_service.py`:

- Reads `GEMINI_API_KEY` from environment  
- Builds a constrained JSON-only prompt  
- Calls Gemini REST `generateContent`  
- Parses/normalizes JSON  
- Returns a structured dict consumed by routes  

### 8.2 Model strategy

Ordered fallback:

1. `gemini-flash-lite-latest` (preferred — faster / freer tier)  
2. `gemini-flash-latest`  

Retries on timeout / `429` / `503` with exponential backoff.

### 8.3 Generation config

- `temperature: 0`, `topP: 1`, `topK: 1` — more deterministic estimates  
- `responseMimeType: application/json`  
- `maxOutputTokens: 2048`  

### 8.4 Failure isolation

AI errors are caught and surfaced as route-level `503`. Movie/episode CRUD does not depend on Gemini availability.

### 8.5 Security / networking notes

- HTTPS to Google uses `certifi` CA bundle (fixes macOS Python SSL issues)  
- API key never returned in responses  

---

## 9. Configuration architecture

### 9.1 Sources

1. Process environment (Railway Variables)  
2. Local `.env` via `load_dotenv()` (gitignored)  

### 9.2 Database URL resolution (`config.py`)

Priority:

1. `DATABASE_PUBLIC_URL` if set  
2. `DATABASE_URL` if not an unreachable `*.railway.internal` host from wrong topology  
3. Local default fallback  

Auto-normalize:

- `postgres://` → `postgresql+psycopg://`  
- `postgresql://` → `postgresql+psycopg://`  

### 9.3 Required env vars

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` / `DATABASE_PUBLIC_URL` | Postgres DSN |
| `GEMINI_API_KEY` | AI preview |
| `PORT` | Railway bind port |

---

## 10. Deployment architecture

### 10.1 Production (Railway)

```
Railway Project
├── Web service (fs_backend)
│     └── uvicorn main:app --host 0.0.0.0 --port $PORT
└── PostgreSQL
      └── linked via DATABASE_URL (same project) OR public URL
```

Build: Nixpacks (`railway.toml`)  
Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 10.2 Local development

```
Mac (uvicorn --host 0.0.0.0 --port 8000)
  ├── Local Postgres (movies_db)  OR  Railway public Postgres
  └── Physical phone on same Wi-Fi → http://<LAN-IP>:8000
```

Binding only to `127.0.0.1` blocks physical devices.

### 10.3 Environments

| Env | DB | AI key | Host |
|-----|----|--------|------|
| Local | Local or Railway public | `.env` | `0.0.0.0:8000` |
| Production | Railway Postgres | Railway Variables | `0.0.0.0:$PORT` |

---

## 11. Cross-cutting concerns

### Dependency injection

- DB sessions via FastAPI `Depends(get_db)`  
- One session per request; closed in `finally`  

### Connection health

- SQLAlchemy `pool_pre_ping=True`  
- Startup retries if Postgres is not ready  

### Error model

| Situation | Typical HTTP |
|-----------|--------------|
| Validation | `422` |
| Missing resource | `404` |
| Duplicate identity | `409` |
| AI/provider failure | `503` |

### Logging

- Standard library logging  
- AI failures logged with stack traces  
- DB host logged at config import (no password)  

### Observability gaps (current)

- No structured metrics/tracing yet  
- No auth/rate limiting yet  

---

## 12. Design decisions (ADRs lite)

| Decision | Rationale |
|----------|-----------|
| Monolith FastAPI service | Simpler ops for current scale |
| Polymorphic `cut_scenes` | One table for movie + episode cuts |
| No SQL FKs on cut_scenes | Flexibility; app-level cascade delete |
| POST create-only / PUT replace | Clear mobile create vs edit semantics |
| Enum skip reasons | Prevent inconsistent free-text tags |
| AI categories separate from DB reasons | AI taxonomy ≠ save taxonomy |
| Gemini over Claude | Free-tier friendlier for previews |
| Postgres ILIKE suggestions | Enough for current catalog size; no Elasticsearch required |
| Destructive schema reset helper | Speed early iteration; migrate to Alembic later |

---

## 13. Threats & risks (architecture-level)

| Risk | Mitigation / note |
|------|-------------------|
| Open CORS | Fine for early mobile; restrict later |
| No auth | Any client with URL can write data |
| AI non-determinism | Temperature 0 + strict prompt; cache later |
| Schema reset drops data | Avoid in mature prod; add migrations |
| Internal Railway DB URL across projects | Prefer same project or public URL |
| Secrets in chat/logs | Keep keys in env only; rotate if exposed |

---

## 14. Future architecture directions

- Alembic versioned migrations  
- AuthN/AuthZ (API keys or user accounts)  
- Cache AI previews in DB for stable repeats  
- SQL FKs or explicit relationship models  
- Episode AI preview endpoints  
- Rate limiting / request quotas  
- Structured logging + metrics  

---

## 15. File map (quick reference)

| File | Architectural role |
|------|--------------------|
| `main.py` | Composition root, middleware, lifespan |
| `routes.py` | HTTP adapters / use-case entrypoints |
| `schemas.py` | External API contracts |
| `models.py` | Persistence model |
| `database.py` | Unit of work / connection lifecycle |
| `ai_service.py` | External AI gateway |
| `config.py` | Environment & DSN policy |
| `railway.toml` | Deploy topology statement |
| `PRD.md` | Product requirements |
| `README.md` | Human project overview |

---

*If implementation drifts from this document, update `ARCHITECTURE.md` in the same change.*
