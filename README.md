# PrimeStride Client OS v0.2

Internal Client Intelligence / Sales Operating System for PrimeStride AI.

## v0.2 focus — guided discovery workflow

A salesperson can now move a company from `Meeting Booked` through a structured Discovery Meeting without leaving Client OS.

### Included
- Pipeline and permanent company record
- Pre-meeting intake
- Guided 8-step Discovery Meeting
- Structured workflow, bottleneck, key-person dependency, quoting, production and management-metric capture
- Customer exact words
- Top 3 pain points
- Module fit ①–⑥
- Discovery completeness score
- Definition-of-Done gate before `Diagnosis Confirmed`
- Required next action + owner + due date
- Meeting history + timeline
- Deterministic post-meeting follow-up draft (AI refinement comes later)
- Existing Data Readiness / task placeholders retained

## Definition of Done for Diagnosis Confirmed
- Discovery completeness >= 75%
- Biggest bottleneck captured
- At least one module marked `High` fit
- Next action captured

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

## Deployment
GitHub is the source of truth and Vercel should deploy from `main` after PR merge.

For production/persistent usage set `DATABASE_URL` to PostgreSQL. SQLite is only for local/demo use.

## Safety / data hygiene
Never commit API keys, database credentials, real client uploads, or confidential customer data.

## Next
- v0.3 Data Request + secure file upload
- v0.4 Data Readiness Engine
- v0.5 Client Blueprint generation
