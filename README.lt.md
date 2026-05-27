# arxivlens — agentinė arXiv filtravimo sistema

> 🇱🇹 Lietuviškai · 🇬🇧 [English](README.md)

Paleidimo instrukcija:

## Portai per kuriuos sąveikaujama

| Sluoksnis        | Technologija                                    | Prievadas |
|------------------|-------------------------------------------------|-----------|
| Vartotojo sąsaja | Next.js 15 (`web_ui/`)                          | 3000      |
| Serveris         | FastAPI + Uvicorn (`backend/`)                  | 8000      |
| Foninis procesas | Celery + Redis (`backend/app/worker/`)          | —         |
| Duomenų bazė     | Postgres 18 + pgvector (docker-compose)         | 5433      |
| Tarpininkas      | Redis 7 (docker-compose)                        | 6379      |
| GPU              | Modal.com (SPECTER2 embeddingai, Marker PDF)    | —         |

## Vienkartinis paruošimas

1. Paleisti **Docker Desktop**.
2. Sukurti **Python `.venv/`** projekto šaknyje su serverio priklausomybėmis:
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate   # Git Bash, Windows
   pip install -r backend/requirements.txt
   ```
3. Įdiegti **Node priklausomybes** vartotojo sąsajai:
   ```bash
   cd web_ui && npm install
   ```
4. Užpildyti **`backend/.env`** — nukopijuoti / pakeisti iš esamo šablono
   (API raktai: OpenAI, Modal, JWT slaptažodis).
5. **Migruoti duomenų bazę**:
   ```bash
   cd backend && alembic upgrade head
   ```

### Modal (GPU)

Serveris perduoda SPECTER2 embeddingų skaičiavimą ir Marker PDF
apdorojimą į Modal aplikaciją (`gpu/gpu_inference.py`).

Kaip suderinti:

1. Užsiregistruoti adresu <https://modal.com> (nemokamo lygio pakanka).
2. Susieti kompiuterį su Modal paskyra — atveria naršyklę
   autentifikacijai:
   ```bash
   modal token new
   ```
   Įrašo prisijungimo duomenis į `~/.modal.toml`.
3. Sukurti Hugging Face žetoną adresu
   <https://huggingface.co/settings/tokens> (reikalingas SPECTER2 svorių
   atsisiuntimui).
4. Sukurti Modal paslaptį pavadinimu `huggingface` su tuo žetonu:
   ```bash
   modal secret create huggingface HF_TOKEN=hf_xxx...
   ```
5. Vieną kartą įdiegti GPU aplikaciją:
   ```bash
   modal deploy gpu/gpu_inference.py
   ```
6. `backend/.env` faile nustatyti `MODAL_GPU_ENABLED=true`.

## Paleidimas — A variantas: `.dev_launchers/` skriptai (rekomenduojama)

Vieną kartą paleisti Postgres + Redis:

```bash
cd backend && docker-compose up -d
```

Tada kiekvieną iš šių skriptų paleisti atskirame terminale (galima
dvigubai spustelėjus arba per Git Bash):

| Skriptas                        | Ką paleidžia              |
|---------------------------------|---------------------------|
| `.dev_launchers/backend.sh`     | FastAPI `:8000` prievade  |
| `.dev_launchers/celery.sh`      | Celery foninis procesas   |
| `.dev_launchers/frontend.sh`    | Next.js `:3000` prievade  |

Kiekvienas langas lieka atviras po proceso pabaigos, kad būtų galima
perskaityti klaidas.

Atidaryti <http://localhost:3000>.

## Paleidimas — B variantas: rankinis

Atidaryti keturis terminalus.

```bash
# 1. Infrastruktūra
cd backend && docker-compose up -d

# 2. Serveris
source .venv/Scripts/activate
cd backend && python -m uvicorn app.main:app --reload --port 8000

# 3. Celery foninis procesas (Windows: --pool=solo)
source .venv/Scripts/activate
cd backend && python -m celery -A app.worker.celery_app worker --pool=solo --loglevel=info --concurrency=1

# 4. Vartotojo sąsaja
cd web_ui && npm run dev
```

## Sustabdymas

```bash
# Ctrl+C kiekviename paleidimo lange, tada:
cd backend && docker-compose down
```

## Pirmojo paleidimo patikra

1. Užsiregistruoti adresu <http://localhost:3000/register>.
2. Skiltyje **Terminal → Filtering** įrašyti filtravimo tikslą
   (laisvas tekstas) ir išsaugoti — tai paleidžia `GoalDistiller`, kuris
   užpildo `distilled_criteria` ir `lexical_query` laukus.
   **Be šio žingsnio konvejeris nutraukiamas.**
3. Paleisti konvejerį iš šoninės juostos; būseną stebėti viršutinėje
   juostoje esančiame indikatoriuje.