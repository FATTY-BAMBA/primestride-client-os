# PrimeStride Client OS v0.1

A working internal MVP for PrimeStride's Client Intelligence / Sales Operating System.

## What is in v0.1

- Pipeline board with persistent company records
- Company stage, owner, next action, due date, fit status
- Discovery record: current flow, bottleneck, key-person dependency, existing systems, baseline, success definition, customer exact words
- Ranked pain points
- Module-fit record
- Data-readiness scores by module
- Tasks with owner/due date/completion
- Timeline of stage/readiness/discovery events
- Demo client preloaded for ④ AI 報價 + ⑤ 工單 + ⑥ AI 數據分析
- SQLite by default for zero-friction local use
- PostgreSQL-ready through `DATABASE_URL`
- Docker Compose with PostgreSQL for a more production-like setup

## Run immediately

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open: http://127.0.0.1:8000

A demo company is automatically created the first time the app runs.

## Run with Docker + PostgreSQL

```bash
docker compose up --build
```

Open: http://127.0.0.1:8000

## Deployment direction

- GitHub is the source of truth.
- Vercel should deploy from this repository.
- Production data should use PostgreSQL, not SQLite.
- Never commit API keys, database credentials, client uploads, or confidential customer data.

## Next build increments

### v0.2 — Meeting workflow
- Pre-meeting intake
- Meeting/discovery run sheet
- Meeting records
- AI-assisted meeting summary (human confirm/edit)
- Definition-of-Done gates before stage movement

### v0.3 — Data request + files
- Personalized data request generated from module fit
- Secure file upload
- File inventory per client
- Data-request status

### v0.4 — Data Readiness Engine
- File classification
- Field detection/mapping
- Completeness/consistency/depth scoring
- What to ask for next / what NOT to ask for

### v0.5 — Client Blueprint
- Current-state workflow
- Proposed future workflow
- Recommended phases
- Auto-drafted follow-up / blueprint presentation

## Architecture direction

v0.1 is a modular monolith. Do not split into microservices yet. Preserve domain boundaries so Client Intelligence, Data Intake, Quoting, Production, Analytics and AI can be extracted later if needed.
