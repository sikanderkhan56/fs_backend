# Product Requirements Document (PRD)

**Product:** FS Backend — Movie / Episode Cut Scenes API  
**Type:** Backend service (REST API)  
**Primary client:** React Native mobile app  
**Status:** Production (Railway)  
**Audience:** Engineers joining the project (backend, mobile, or full-stack)

---

## 1. Overview

### 1.1 Product summary

FS Backend is an API that lets a mobile app **skip selected scenes** while playing movies or web series episodes. Users can save exact skip intervals (`start` / `end` in seconds), look up existing data, edit it, and — when nothing is saved yet — get **AI-estimated** timelines for kissing, sexual content, and nudity.

### 1.2 Problem statement

Content-conscious viewers often want to avoid specific scenes (especially romantic/sexual content) without avoiding the whole film or episode. Doing this well needs:

- Stable identity for titles (including remakes and episodes)
- Shared, reusable skip data across sessions/devices
- A way to bootstrap suggestions when no community/user data exists yet
- Clear, validated reason categories (not free-text chaos)

### 1.3 Solution

A FastAPI + PostgreSQL service that:

1. Stores **exact** cut scenes for movies and episodes  
2. Exposes CRUD + search + autocomplete for the mobile client  
3. Uses **Google Gemini** for estimated scene previews when DB data is missing  
4. Enforces enums and uniqueness rules so data stays consistent  

### 1.4 Non-goals (out of scope for this backend)

- Video streaming or playback itself (client-side player)
- User accounts / auth / multi-tenant permissions (not implemented yet)
- Exact frame-accurate AI timestamps (AI is estimate-only)
- Flagging violence/guns/fighting via AI (explicitly excluded from AI preview)
- Full-text search engine (Elasticsearch); autocomplete uses PostgreSQL `ILIKE`

---

## 2. Goals & success criteria

### 2.1 Goals

| ID | Goal |
|----|------|
| G1 | Persist exact skip scenes for movies and web series episodes |
| G2 | Support remakes via title + release year |
| G3 | Support series via series title + season + episode |
| G4 | Enable Play vs Edit UX when data already exists |
| G5 | Provide AI estimates for kissing / sex / nudity when no DB data |
| G6 | Keep API contracts strict (Pydantic + enums) for reliable mobile integration |

### 2.2 Success criteria

- Client can create, read, update, delete cut data without schema ambiguity  
- Duplicate titles with different years do not collide  
- Same series season/episode does not create conflicting rows  
- AI preview never returns violence/gun/fight categories  
- Invalid skip reasons are rejected with `422`  
- Production API is reachable and documented at `/docs`  

---

## 3. Users & personas

| Persona | Needs |
|---------|--------|
| Mobile end user | Skip unwanted scenes; reuse saved data; get AI hints for new titles |
| Mobile developer | Clear endpoints, stable JSON contracts, predictable errors |
| Backend developer | Clear domain rules, DB model, AI boundaries, deployment constraints |

This PRD is written mainly for **developers**. Product behavior is described so implementation stays aligned.

---

## 4. Product concepts

### 4.1 Content types

| Type | Identity | Example |
|------|----------|---------|
| Movie | `title` + `release_year` (+ `movie_id`) | Hitman (2007) vs Hitman (2015) |
| Episode | `series_title` + `season_number` + `episode_number` (+ `episode_id`) | Game of Thrones S8 E6 |

### 4.2 Cut scene (exact, stored)

A skip segment saved in PostgreSQL:

- `start` / `end` — float seconds  
- `reason` — one of: `violence`, `inappropriate`, `eighteen_plus`  
  - (`unknown` only for legacy reads; do not use on create/update)

### 4.3 AI estimated scene (preview only)

Returned by Gemini, **not** the same enum as DB reasons:

- Categories: `Kissing`, `Sexual Content`, `Nudity`  
- Time format: approximate string, e.g. `~01:12:00-01:14:30`  
- Must be confirmed by the user (frame-by-frame) before saving as exact cuts  

When saving AI suggestions into DB, the client must **map** AI categories to DB `reason` enums (e.g. nudity/sex/kissing → `eighteen_plus` or `inappropriate`).

---

## 5. Functional requirements

### 5.1 Movies

| ID | Requirement |
|----|-------------|
| M1 | Create a movie with metadata + list of cut scenes |
| M2 | Prevent duplicate `movie_id` and duplicate `(title, release_year)` |
| M3 | Fetch movie + cut scenes by `movie_id` |
| M4 | Fetch movie + cut scenes by `title` + `release_year` |
| M5 | Check whether a movie exists (for Play / Edit UI) |
| M6 | Suggest movies by partial title (autocomplete) |
| M7 | Update movie metadata and **replace** entire cut scene list |
| M8 | Delete movie and its cut scenes |

### 5.2 Episodes (web series)

| ID | Requirement |
|----|-------------|
| E1 | Create an episode with series/season/episode + cut scenes |
| E2 | Auto-generate `episode_id` slug if client omits it |
| E3 | Prevent duplicate identity (series + season + episode) |
| E4 | Fetch by ID or by series/season/episode search |
| E5 | Exists check for Play / Edit UI |
| E6 | Update with full cut scene replace |
| E7 | Delete episode and its cut scenes |

### 5.3 Cut scenes

| ID | Requirement |
|----|-------------|
| C1 | Cut scenes belong to either a movie or an episode (`content_type`) |
| C2 | Times are floats in **seconds** |
| C3 | Reasons must match allowed enum on write |
| C4 | Update endpoints replace the full scene list (not partial patch) |

### 5.4 AI preview (movies)

| ID | Requirement |
|----|-------------|
| A1 | `POST .../preview-scenes` always queries Gemini |
| A2 | `GET .../preview-scenes` returns DB cuts if movie exists; otherwise AI |
| A3 | AI may only report Kissing / Sexual Content / Nudity |
| A4 | AI must exclude violence, guns, fighting, cheek kisses, etc. |
| A5 | AI failures return clear errors (e.g. `503`) without crashing the whole API |
| A6 | Responses must state that times are estimates |

### 5.5 Utility

| ID | Requirement |
|----|-------------|
| U1 | Health endpoint `GET /` |
| U2 | `GET /api/skip-reasons` returns selectable DB reason labels |
| U3 | OpenAPI docs available at `/docs` |

---

## 6. User / client flows

### 6.1 Movie — first time save

```
User picks Movie
  → enter title + release year (+ duration)
  → optional: AI preview
  → mark exact cut scenes
  → POST /api/movie
  → play using saved start/end seconds
```

### 6.2 Movie — already exists

```
User enters title + year
  → GET /api/movie/exists
  → if exists:
       Play  → GET /api/movie/{id} or /search
       Edit  → load scenes → edit list → PUT /api/movie/{id}
  → if not:
       create flow (6.1)
```

### 6.3 Movie — AI assist when empty

```
GET or POST /api/movie/{id}/preview-scenes?title=&release_year=
  → if source=database: use cut_scenes (exact)
  → if source=ai_preview: show estimated_scenes
  → user confirms timings
  → map AI categories → DB reasons
  → POST or PUT /api/movie
```

### 6.4 Episode flows

Same as movies, using `/api/episode/*` and series / season / episode fields.

### 6.5 Autocomplete

```
User types title
  → debounced GET /api/movie/suggestions?query=
  → show title + year (+ scene_count)
  → on select: fill title/year/id and continue exists/play flow
```

---

## 7. API requirements (contracts)

Base URL pattern: `{host}/api`

Interactive docs: `{host}/docs`

### 7.1 Movies

| Method | Path | Notes |
|--------|------|-------|
| GET | `/movie/suggestions` | Query: `query`, optional `limit` |
| GET | `/movie/exists` | Query: `title`, `release_year` |
| POST | `/movie` | Body: MovieSchema → `201` |
| GET | `/movie/search` | Query: `title`, `release_year` |
| GET | `/movie/{movie_id}` | Path id |
| PUT | `/movie/{movie_id}` | Full scene replace |
| DELETE | `/movie/{movie_id}` | Cascades cut scenes |

### 7.2 Episodes

| Method | Path | Notes |
|--------|------|-------|
| GET | `/episode/exists` | series_title, season_number, episode_number |
| POST | `/episode` | Body: EpisodeSchema → `201` |
| GET | `/episode/search` | series + season + episode |
| GET | `/episode/{episode_id}` | Path id |
| PUT | `/episode/{episode_id}` | Full scene replace |
| DELETE | `/episode/{episode_id}` | Cascades cut scenes |

### 7.3 AI preview

| Method | Path | Notes |
|--------|------|-------|
| POST | `/movie/{movie_id}/preview-scenes` | Query: title, release_year; always AI |
| GET | `/movie/{movie_id}/preview-scenes` | DB first, else AI |

### 7.4 Expected status codes

| Code | Meaning |
|------|---------|
| `200` | Success (read/update/delete/preview) |
| `201` | Created |
| `404` | Not found |
| `409` | Conflict (duplicate) |
| `422` | Validation error (bad body / enum) |
| `503` | AI / dependency unavailable |

---

## 8. Data model requirements

### 8.1 Tables

**movies** — unique `movie_id`; unique `(title, release_year)`  
**episodes** — unique `episode_id`; unique `(series_title, season_number, episode_number)`  
**cut_scenes** — `content_type` + `reference_id` + timing + reason  

### 8.2 Integrity rules

- Creating a movie/episode that already exists by business key → `409`  
- Updating must not collide with another row’s unique key  
- Deleting parent content deletes associated cut scenes  

### 8.3 Schema evolution

App startup may detect legacy schemas and recreate content tables when required (dev/early-prod tradeoff). Formal Alembic migrations are a future improvement.

---

## 9. AI product rules (strict)

### Must include

1. Mouth-to-mouth / French kiss (any pairing)  
2. Sexual intercourse or clear sexual activity  
3. Nudity: naked body, breasts, hips/buttocks, or private parts  

### Must exclude

- Cheek / forehead / hand kisses, quick pecks  
- Violence, guns, killing, fighting, blood  
- Language, drugs, horror, non-sexual intensity  
- Swimwear/underwear without clear private-part exposure  

### Quality rules

- Approximate times only (`~`)  
- Chronological order preferred  
- Cap on number of scenes  
- Prefer stable output (low/zero temperature)  
- Retries + model fallback for reliability  

---

## 10. Non-functional requirements

| Area | Requirement |
|------|-------------|
| Performance | Autocomplete and exists checks should feel snappy for mobile typing |
| Reliability | AI failures must not take down unrelated CRUD endpoints |
| Security | Secrets via env vars; never commit `.env` |
| Compatibility | CORS open for mobile clients (`*` origins in current setup) |
| Observability | Log AI failures; expose OpenAPI at `/docs` |
| Deploy | Bind `0.0.0.0` + `$PORT` on Railway; LAN bind for physical devices locally |

---

## 11. Client integration notes (for mobile team)

1. **Do not send free-text reasons** — map to `violence` / `inappropriate` / `eighteen_plus`  
2. **AI categories ≠ DB reasons** — map before POST/PUT  
3. Prefer `GET /exists` before create to avoid `409` / improve UX  
4. Treat AI times as hints; confirm before saving exact seconds  
5. Debounce suggestion calls (~300–500ms)  
6. Physical device: use machine LAN IP with server `--host 0.0.0.0`  

---

## 12. System context

```
┌─────────────────────┐
│  React Native App   │
│  (physical / emu)   │
└──────────┬──────────┘
           │ HTTPS / HTTP
           ▼
┌─────────────────────┐
│  FastAPI Backend    │
│  routes + schemas   │
└───────┬─────────────┘
        │
   ┌────┴─────┐
   ▼          ▼
PostgreSQL   Gemini API
(exact data) (estimates)
```

---

## 13. Future / backlog (not committed)

- Auth (users, ownership of cut lists)
- Cache AI previews in DB for stable repeat results
- Partial patch for individual cut scenes
- Alembic migrations
- Episode AI preview endpoints
- Rate limiting / API keys
- Soft-delete / audit history

---

## 14. Related documents

| Doc | Purpose |
|-----|---------|
| `README.md` | Project overview for humans |
| `PRD.md` (this file) | Product + engineering requirements |
| `ARCHITECTURE.md` | Full system design |
| `ARCHITECTURE-ESSENTIALS.md` | Critical architecture decisions (quick ref) |
| `AGENTS.md` | Guidance for AI coding agents |
| `GETTING_STARTED.md` | Installation & local/Railway setup |
| `/docs` (runtime) | Live OpenAPI / Swagger |

---

## 15. Changelog snapshot (product)

- Movies + episodes CRUD with cut scenes  
- Exists / search / autocomplete  
- Enum skip reasons  
- Gemini AI preview for movies (kissing / sex / nudity only)  
- Railway production deployment  

---

*This PRD describes the product as implemented. If behavior and this document disagree, update the PRD or the code — do not leave them drifting.*
