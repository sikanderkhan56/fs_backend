# Getting Started — Installation & Setup

Step-by-step guide to run **FS Backend** on your machine (and connect a physical phone).

For project overview see [`README.md`](./README.md).  
For product rules see [`PRD.md`](./PRD.md).

---

## Prerequisites

Install these first:

| Tool | Notes |
|------|--------|
| **Python 3.10+** | 3.12 recommended (matches Railway). 3.8 may work with limits. |
| **pip** | Comes with Python / venv |
| **PostgreSQL** | Local install, or use a Railway public DB URL |
| **Git** | To clone the repo |
| **Gemini API key** (optional) | Only needed for AI preview — [Google AI Studio](https://aistudio.google.com/apikey) |

Check versions:

```bash
python3 --version
psql --version
```

---

## 1. Clone the repository

```bash
git clone <your-repo-url>
cd fs_backend
```

---

## 2. Create and activate a virtual environment

```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
# venv\Scripts\activate
```

Your prompt should show `(venv)`.

If `pip` is not found outside the venv, always activate the venv first, or use:

```bash
python3 -m pip install -r requirements.txt
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

Main packages: FastAPI, Uvicorn, SQLAlchemy, psycopg, Pydantic, python-dotenv, certifi.

---

## 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

### Option A — Local PostgreSQL (recommended for development)

```env
DATABASE_URL=postgresql://YOUR_MAC_USERNAME@localhost/movies_db
GEMINI_API_KEY=your_gemini_key_here
```

On macOS, `YOUR_MAC_USERNAME` is often your login name (e.g. `apple`). No password is usually required for local trust auth.

Create the database:

```bash
createdb movies_db
```

If it already exists, that is fine.

### Option B — Railway Postgres (remote DB from your laptop)

Use the **public** URL from Railway → Postgres → Connect (host like `*.proxy.rlwy.net`), **not** `postgres.railway.internal`:

```env
DATABASE_URL=postgresql://postgres:PASSWORD@xxxx.proxy.rlwy.net:PORT/railway
GEMINI_API_KEY=your_gemini_key_here
```

### Gemini key

1. Open [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)  
2. Create a key  
3. Set `GEMINI_API_KEY=...` in `.env`  

Without this key, CRUD still works; AI preview endpoints return `503`.

**Never commit `.env`.** It is gitignored.

---

## 5. Run the server

### Browser / same machine only

```bash
uvicorn main:app --reload
```

- API: http://127.0.0.1:8000  
- Docs: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/

### Physical phone (same Wi‑Fi) — required bind

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Find your Mac LAN IP:

```bash
ipconfig getifaddr en0
```

Example: `192.168.1.12`

On the phone / React Native app use:

```text
http://192.168.1.12:8000
```

Tables are created automatically on startup (`init_db`).

---

## 6. Verify installation

```bash
# Health
curl http://127.0.0.1:8000/

# Skip reasons
curl http://127.0.0.1:8000/api/skip-reasons

# Open Swagger UI in a browser
open http://127.0.0.1:8000/docs
```

Expected health response:

```json
{"message": "Movie Backend API"}
```

Optional AI check (needs `GEMINI_API_KEY`):

```bash
curl -X POST "http://127.0.0.1:8000/api/movie/inception-2010/preview-scenes?title=Inception&release_year=2010"
```

---

## 7. Deploy on Railway (optional)

1. Create a Railway project.  
2. Add **PostgreSQL** (preferably in the **same** project as the API).  
3. Deploy this GitHub repo as a service.  
4. Set variables on the API service:

| Variable | Value |
|----------|--------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (variable reference) **or** public URL |
| `GEMINI_API_KEY` | Your Gemini key |

5. Ensure start command (already in `railway.toml`):

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

6. Open the generated `*.up.railway.app` URL and `/docs`.

**Note:** `postgres.railway.internal` only works when API and Postgres are in the same Railway project.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `zsh: command not found: pip` | Activate `venv`, or use `python3 -m pip` |
| `role "user" does not exist` | Use your macOS username in `DATABASE_URL`, not `user` |
| App works on Mac, not on phone | Use `--host 0.0.0.0` and LAN IP, same Wi‑Fi |
| `GEMINI_API_KEY is not configured` | Set key in `.env` (local) or Railway Variables (prod) |
| SSL certificate error calling Gemini (local Mac) | Ensure `certifi` is installed (`pip install -r requirements.txt`) |
| Gemini timeout / 503 high demand | Retry; service falls back across Gemini models |
| `422` on `POST /api/movie` | `reason` must be `violence`, `inappropriate`, or `eighteen_plus` — not `"other"` or AI labels |
| `failed to resolve host 'postgres.railway.internal'` | Use public URL locally, or same-project DB reference on Railway |
| Schema / missing column errors after upgrades | Early project may reset legacy tables on startup — back up prod data first |

---

## Daily workflow (after first setup)

```bash
cd fs_backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Stop with `Ctrl+C`.

---

## Related docs

| Doc | Purpose |
|-----|---------|
| `GETTING_STARTED.md` | This file — install & run |
| `README.md` | What the project is |
| `PRD.md` | Product requirements |
| `ARCHITECTURE.md` | Full architecture |
| `ARCHITECTURE-ESSENTIALS.md` | Architecture cheat sheet |
| `AGENTS.md` | Guidance for AI coding agents |
