# Friction Hackathon Integrated Backend

This package combines:
- Member 1 FastAPI + deterministic friction pipeline
- Member 3 tested AI/ML analyzer (`app/ai_analyzer.py`)
- Member 4 CSV event contract (`data/events.csv`)
- React live-event ingestion endpoint: `POST /events`

## Run
From this `friction-backend` folder:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

If your `.venv` is already activated:

```powershell
uvicorn app.main:app --reload --port 8000
```

Open:
http://localhost:8000/docs

## Member 3
The AI analyzer has been integrated through `app/ai_bridge.py`.
The adapter exposes:
`analyze(analysis, events) -> {cause, evidence, confidence, recommendation, ...}`

It uses the tested rule-based analyzer and does not require an API key.

## Member 4
The dataset follows:
`customer_id,timestamp,event_type,metadata,session_id`

The existing `data/events.csv` contains synthetic sessions covering:
payment failures, price shock, delivery uncertainty, product information friction,
successful purchases and exits.

## Live frontend
The React tracker can POST events to:
`http://localhost:8000/events`

The endpoint appends the event to `data/events.csv` and reloads the in-memory pipeline.
For the demo, use a stable `session_id` from the frontend so all actions stay in one session.

## Important
This is a hackathon prototype. Scores are rule-based heuristics, not statistically
validated probabilities.
