# Trust Layer MVP

A reputation-based decision system for AI agents. Trust Layer evaluates pre-supplied candidate outputs from multiple agents, computes Trust Scores, ranks candidates deterministically, selects a winner, and updates agent reputation over time.

**Core concept:** agentic reputation → trust score → decision

## What the MVP Demonstrates

- Persistent agent reputation profiles
- Whole-word keyword relevancy scoring
- Trust Score computation: `0.6 × success_rate + 0.4 × relevancy`
- Deterministic ranking with tie-break rules
- Winner selection and structural outcome validation
- Winner-only reputation update with persistence
- Full evaluation loop observable via browser UI and structured logs

## Folder Structure

```
trust-layer/
├── api/                  # Vercel serverless handlers (BaseHTTPRequestHandler)
│   ├── health.py         # GET  /api/health
│   ├── state.py          # GET  /api/state
│   ├── run_demo.py       # POST /api/run-demo
│   └── reset.py          # POST /api/reset
├── core/                 # Pure Python engine (zero web dependencies)
│   ├── models.py         # Data models
│   ├── scoring.py        # ScoringEngine
│   ├── store.py          # ReputationStore (MemoryStore + RedisStore)
│   ├── controller.py     # TrustController
│   ├── config.py         # Scoring config loader
│   └── fixtures.py       # Demo task + seed profiles loader
├── data/                 # Read-only fixture files
│   ├── demo_task.json
│   └── seed_profiles.json
├── public/               # Static frontend (no framework)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tests/                # pytest test suite
│   ├── conftest.py
│   ├── test_scoring.py
│   ├── test_store.py
│   └── test_controller.py
├── config/
│   └── scoring.json      # Scoring weights
├── requirements.txt
├── vercel.json
└── README.md
```

## How to Run Tests

```bash
cd trust-layer
pip install -r requirements.txt
python -m pytest tests/ -v
```

Tests use `MemoryStore` (in-memory) and do not require Redis or any external service.

## How to Deploy on Vercel

1. Push to GitHub
2. Import project in Vercel
3. Add a Vercel KV (Upstash Redis) store from the Vercel dashboard
4. Environment variables are auto-configured:
   - `UPSTASH_REDIS_REST_URL`
   - `UPSTASH_REDIS_REST_TOKEN`
5. Deploy

## Intentionally Out of Scope (Phase 1)

- No real LLM API calls
- No semantic or embedding-based relevancy
- No loser reputation updates
- No custom task input via UI
- No run history
- No authentication
- No quality-based outcome evaluation (structural check only)
