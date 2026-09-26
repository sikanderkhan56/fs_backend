# AGENTS.md

Instructions for **AI coding agents** (and humans) working in this repository.

Read this before changing code. For product rules see `PRD.md`. For full design see `ARCHITECTURE.md`. For a short architecture cheat sheet see `ARCHITECTURE-ESSENTIALS.md`.

---

## 1. Project snapshot

| Item | Value |
|------|--------|
| Name | FS Backend — Movie Cut Scenes API |
| Stack | FastAPI · SQLAlchemy · PostgreSQL · Pydantic · Gemini |
| Role | Backend API for a React Native client |
| Layout | Flat Python package at repo root (no `src/` package) |

**Purpose:** Store exact skip scenes for movies/episodes; optionally return Gemini AI estimates for kissing / sexual content / nudity when DB data is missing.

---

## 2. Read these docs first

| Priority | Doc | When |
|----------|-----|------|
| 1 | `ARCHITECTURE-ESSENTIALS.md` | Always — critical decisions |
| 2 | `PRD.md` | Product / API behavior questions |
| 3 | `ARCHITECTURE.md` | Deep design / data model |
| 4 | `README.md` | High-level overview |
| Runtime | `/docs` | Live OpenAPI |

Do **not** invent endpoints, enums, or tables that contradict these docs.

---

## 3. Repository map

| File | Change when… |
|------|----------------|
| `main.py` | App lifespan, middleware, root route |
| `routes.py` | HTTP endpoints / request orchestration |
| `schemas.py` | Request/response contracts, enums |
| `models.py` | SQLAlchemy tables / constraints |
| `database.py` | Engine, sessions, schema init |
| `ai_service.py` | Gemini prompt, models, retries |
| `config.py` | Env vars / DSN resolution |
| `requirements.txt` | Dependencies |
| `railway.toml` | Deploy start command |
| `.env.example` | Documented env keys (no secrets) |

Do not commit `.env` or real API keys / DB passwords.

---

## 4. Hard product rules (do not break)

### Identity

- Movies: unique `movie_id` **and** unique `(title, release_year)`
- Episodes: unique `episode_id` **and** unique `(series_title, season_number, episode_number)`

### Cut scenes

- Times are **seconds** (`float`)
- Saved `reason` must be: `violence` | `inappropriate` | `eighteen_plus`
- `unknown` is legacy-read only — never require it on create/update
- `PUT` **replaces** the full cut list (not partial patch)

### HTTP semantics

- `POST` = create only → `201` or `409`
- `PUT` = update/replace
- Invalid body → `422`
- Missing → `404`
- AI failure → `503` (do not crash CRUD)

### AI preview

- Only categories: `Kissing`, `Sexual Content`, `Nudity`
- Exclude violence, guns, fighting, cheek kisses
- Times are estimates with `~` — never claim exact AI timestamps
- Prefer DB data on `GET .../preview-scenes`; `POST` always hits AI

### Client mapping

AI categories ≠ DB reasons. Agents should not “fix” this by accepting AI category strings as `reason` unless product explicitly changes the enum.

---

## 5. Coding conventions

- Prefer small, focused diffs; match existing style in touched files
- Keep layers clear: routes → schemas/models/ai_service (avoid dumping business logic into `main.py`)
- Use Pydantic for API boundaries; SQLAlchemy for persistence
- Case-insensitive title/series matching helpers already exist in `routes.py` — reuse them
- Search routes must be registered **before** `/{id}` path params
- When adding env vars: update `config.py` + `.env.example` (+ docs if behavior changes)
- Update `PRD.md` / `ARCHITECTURE*.md` / `README.md` when behavior or structure changes

### Python notes

- Project historically ran on older local Python; prefer syntax compatible with the deployed Railway Python when possible
- Use `Optional[X]` / `List[X]` if targeting older interpreters; avoid introducing breakage casually
- Gemini HTTPS must keep using `certifi` (macOS SSL issues)

---

## 6. Safe change checklist

Before finishing a task:

1. Confirm enums / uniqueness / POST-vs-PUT semantics still hold  
2. If schema changes: update `models.py` + consider `database.py` legacy detection  
3. If AI prompt/categories change: update `ai_service.py` + PRD AI section  
4. If new endpoint: add to README/PRD API tables and keep OpenAPI accurate  
5. Do not log secrets (`GEMINI_API_KEY`, DB passwords)  
6. Prefer not to run destructive DB resets against production data  

---

## 7. Common tasks → where to edit

| Task | Primary files |
|------|----------------|
| New endpoint | `routes.py`, `schemas.py` |
| New DB field | `models.py`, `schemas.py`, maybe `database.py` |
| Change skip reasons | `schemas.py`, routes labels, PRD/README |
| Change AI rules | `ai_service.py`, PRD § AI |
| Env / Railway DSN | `config.py`, `.env.example` |
| Startup / CORS | `main.py` |

---

## 8. Verification hints

```bash
# Local (after venv + deps)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Health
curl http://127.0.0.1:8000/

# OpenAPI
open http://127.0.0.1:8000/docs
```

Physical device testing requires `--host 0.0.0.0` and the machine LAN IP.

Production: https://fsbackend-production-8079.up.railway.app/docs

---

## 9. What agents should NOT do

- Do not add Elasticsearch unless explicitly requested (Postgres suggestions are intentional)
- Do not broaden AI categories to violence/guns without product approval
- Do not accept free-text `reason` on create/update
- Do not put secrets in docs, commits, or example responses
- Do not force-push / rewrite git history unless the user explicitly asks
- Do not invent auth/users tables without a product request
- Do not replace the whole architecture with a new framework casually

---

## 10. Suggested commit / PR hygiene

- Prefer clear, why-focused messages  
- Mention API/schema/AI breaking changes in the summary  
- Keep installation steps out of `README.md` until a dedicated install doc exists  

---

## 11. Doc index

| File | Role |
|------|------|
| `AGENTS.md` | Instructions for agents working in this repo |
| `README.md` | Project overview |
| `GETTING_STARTED.md` | Install & run |
| `PRD.md` | Product requirements |
| `ARCHITECTURE.md` | Full architecture |
| `ARCHITECTURE-ESSENTIALS.md` | Architecture cheat sheet |

---

*When in doubt: preserve existing API contracts, keep AI constrained, and update docs with the code.*
