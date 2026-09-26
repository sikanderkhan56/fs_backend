# Architecture Essentials

**Quick reference** for critical architecture decisions.  
For full detail see [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## What this service is

FastAPI backend that stores **exact skip scenes** for movies/episodes in PostgreSQL and optionally returns **Gemini AI estimates** (kissing / sex / nudity only).

```
React Native  →  FastAPI  →  PostgreSQL
                    └─────→  Gemini (preview only)
```

---

## Tech stack (critical)

| Piece | Choice |
|-------|--------|
| API | FastAPI + Uvicorn |
| DB | PostgreSQL + SQLAlchemy + psycopg3 |
| Validation | Pydantic v2 enums |
| AI | Gemini REST (`flash-lite` → `flash` fallback) |
| Deploy | Railway (`0.0.0.0:$PORT`) |

---

## Layer map

| Layer | File(s) |
|-------|---------|
| Entry / CORS / lifespan | `main.py` |
| HTTP routes | `routes.py` |
| Contracts | `schemas.py` |
| Tables | `models.py` |
| Sessions / init | `database.py` |
| AI gateway | `ai_service.py` |
| Env / DSN | `config.py` |

---

## Data model (must know)

```
movies  (unique: movie_id, and title+release_year)
episodes (unique: episode_id, and series+season+episode)
cut_scenes (content_type + reference_id → movie_id | episode_id)
```

| Stored reason (DB) | AI category (preview only) |
|--------------------|----------------------------|
| `violence` | `Kissing` |
| `inappropriate` | `Sexual Content` |
| `eighteen_plus` | `Nudity` |

AI categories **must be mapped** by the client before `POST`/`PUT`.

No SQL FKs on `cut_scenes` — app deletes related rows.

---

## API semantics (must know)

| Verb | Meaning here |
|------|----------------|
| `POST` | Create only → `201` / `409` |
| `PUT` | Replace metadata + **entire** cut list |
| `GET /exists` | Drive Play vs Edit UI |
| `GET preview` | DB first, else AI |
| `POST preview` | Always AI |

Important statuses: `422` validation · `409` duplicate · `404` missing · `503` AI down

---

## Critical decisions

1. **Monolith FastAPI** — one deployable service  
2. **Polymorphic cut_scenes** — one table for movie + episode  
3. **Remakes** identified by `title + release_year`  
4. **Episodes** identified by `series + season + episode`  
5. **Strict enums** for saved reasons (no free text)  
6. **AI is fallback / assist only** — not source of truth  
7. **AI excludes violence/guns/fighting** by prompt policy  
8. **Postgres ILIKE autocomplete** — no Elasticsearch  
9. **Startup schema reset** for legacy tables — temporary; Alembic later  
10. **Secrets only in env** — never commit `.env`

---

## Request flow (one glance)

**CRUD:** validate → DB session → commit → JSON → close session  

**AI preview:** if GET and found in DB → exact cuts; else Gemini → estimates (`~` times)

**Startup:** retry `init_db` until Postgres ready

---

## Config essentials

| Env | Purpose |
|-----|---------|
| `DATABASE_URL` or `DATABASE_PUBLIC_URL` | Postgres |
| `GEMINI_API_KEY` | AI preview |
| `PORT` | Railway bind |

`*.railway.internal` only works when API + DB are in the **same** Railway project.

---

## Failure isolation

- Bad body → `422` (CRUD still fine)  
- Gemini timeout/overload → retries + model fallback → else `503`  
- CRUD endpoints do **not** require Gemini  

---

## Deploy essentials

| Env | Bind | DB |
|-----|------|----|
| Local (phone) | `--host 0.0.0.0 --port 8000` | Local or Railway public |
| Production | `0.0.0.0:$PORT` | Railway Postgres |

---

## Not in scope (yet)

Auth · Alembic · AI result caching · Episode AI preview · Rate limits · SQL FKs on cuts

---

## Related docs

| Doc | Use when |
|-----|----------|
| `ARCHITECTURE-ESSENTIALS.md` | Fast onboarding / daily reference |
| `ARCHITECTURE.md` | Deep dive |
| `PRD.md` | Product rules & requirements |
| `README.md` | Project overview |
| `AGENTS.md` | Rules for AI agents editing this repo |
| `GETTING_STARTED.md` | Install and run |
