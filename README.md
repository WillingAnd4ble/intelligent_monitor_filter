# arxivlens — Agent-based arXiv Filtering

> 🇬🇧 English · 🇱🇹 [Lietuviškai](README.lt.md)

How to setup and run

## Ports

| Layer    | Tech                                            | Port |
|----------|-------------------------------------------------|------|
| Frontend | Next.js 15 (`web_ui/`)                          | 3000 |
| Backend  | FastAPI + Uvicorn (`backend/`)                  | 8000 |
| Worker   | Celery + Redis (`backend/app/worker/`)          | —    |
| Database | Postgres 18 + pgvector (docker-compose)         | 5433 |
| Broker   | Redis 7 (docker-compose)                        | 6379 |
| GPU      | Modal.com (SPECTER2 embeddings, Marker PDF)     | —    |

## Prerequisites (one-time)

1. **Docker Desktop** running
2. **Python `.venv/`** at repo root with backend deps installed
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate   # Git Bash on Windows
   pip install -r backend/requirements.txt
   ```
3. **Node modules** for the frontend
   ```bash
   cd web_ui && npm install
   ```
4. **`backend/.env`** — copy/edit from any existing template (API keys: OpenAI, Modal, JWT secret)
5. **Database migrated**
   ```bash
   cd backend && alembic upgrade head
   ```

### Modal (GPU) 

The backend offloads embeddings and PDF extraction to a Modal app
(`gpu/gpu_inference.py`).

How to setup
1. Sign up at <https://modal.com> (free tier is enough).
2. Link your machine — opens a browser to authenticate:
   ```bash
   modal token new
   ```
   Writes credentials to `~/.modal.toml`.
3. Get a Hugging Face token at <https://huggingface.co/settings/tokens>
   (needed to download SPECTER2 weights).
4. Create a Modal secret named `huggingface` holding it:
   ```bash
   modal secret create huggingface HF_TOKEN=hf_xxx...
   ```
5. Deploy the GPU app once:
   ```bash
   modal deploy gpu/gpu_inference.py
   ```
6. In `backend/.env`, set `MODAL_GPU_ENABLED=true`.

## Run — Option A: `.dev_launchers/` scripts (recommended)

Start Postgres + Redis once:

```bash
cd backend && docker-compose up -d
```

Then double-click (or run in Git Bash) each of these in its own terminal:

| Script                          | What it starts       |
|---------------------------------|----------------------|
| `.dev_launchers/backend.sh`     | FastAPI on `:8000`   |
| `.dev_launchers/celery.sh`      | Celery worker        |
| `.dev_launchers/frontend.sh`    | Next.js on `:3000`   |

Each window stays open on exit so you can read errors.

Open <http://localhost:3000>.

## Run — Option B: manual

Open four terminals.

```bash
# 1. Infrastructure
cd backend && docker-compose up -d

# 2. Backend
source .venv/Scripts/activate
cd backend && python -m uvicorn app.main:app --reload --port 8000

# 3. Celery worker (Windows: --pool=solo)
source .venv/Scripts/activate
cd backend && python -m celery -A app.worker.celery_app worker --pool=solo --loglevel=info --concurrency=1

# 4. Frontend
cd web_ui && npm run dev
```

## Stop

```bash
# Ctrl+C in each launcher window, then
cd backend && docker-compose down
```

## First-run sanity check

1. Register at <http://localhost:3000/register>
2. In **Terminal → Filtering**, set a filtering goal (free text) and save —
   this triggers `GoalDistiller`, populating `distilled_criteria` and
   `lexical_query`. **Without this the pipeline aborts.**
3. Trigger the pipeline from the sidebar; watch progress in the topbar pill.
