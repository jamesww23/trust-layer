# Trust Layer MVP

A reputation-based decision system for AI agents. Trust Layer evaluates candidate outputs from multiple agents, computes Trust Scores based on keyword relevancy and historical reputation, ranks candidates deterministically, selects a winner, and updates agent reputation over time.

**Core concept:** agentic reputation → trust score → decision

## What the MVP Demonstrates

- **Persistent agent reputation** — 3 seed agents (GPT-4, Claude, LLaMA) with success rates that evolve across evaluations
- **Trust Score computation** — `0.6 × success_rate + 0.4 × relevancy` with whole-word keyword matching
- **Deterministic ranking** — tie-break by total runs, then agent ID (lexicographic)
- **Winner-only reputation update** — winner's success rate adjusts; losers unchanged
- **Human feedback override** — correct an evaluation outcome and retroactively adjust reputation
- **Run history** — every evaluation is persisted and browsable
- **Custom evaluation** — paste outputs from any agents, select from dropdown, score and rank them
- **4 demo scenarios** — renewable energy, healthcare, finance, cybersecurity

## Frontend

Three tabs:

1. **Try a Demo** — pick a scenario, view pre-loaded agent outputs, run evaluation
2. **Evaluate Agents** — enter a task, select agents (GPT-4 / Claude / LLaMA), paste outputs, run evaluation
3. **History** — browse all past evaluation runs

Agent Leaderboard sidebar shows current rankings with success rates.

## API Surface

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Liveness check |
| `/api/state` | GET | Current profiles, task, candidates, config, scenarios |
| `/api/run-demo` | POST | Run evaluation with demo/scenario task |
| `/api/run-custom` | POST | Run evaluation with user-provided task and candidates |
| `/api/run-llm` | POST | Generate candidates from LLM providers, then evaluate |
| `/api/run-batch` | POST | Run multiple evaluations (scenarios or repeat mode) |
| `/api/feedback` | POST | Override a run's outcome, adjust winner's reputation |
| `/api/create-task` | POST | Create a task for external agents |
| `/api/submit-output` | POST | Queue an agent output for a task |
| `/api/evaluate-task` | POST | Evaluate queued submissions (min 2) |
| `/api/runs` | GET | Fetch run history (paginated) |
| `/api/reset` | POST | Wipe all state and re-seed |

## Folder Structure

```
trust-layer/
├── api/                  # Vercel serverless handlers
│   ├── health.py         # GET  /api/health
│   ├── state.py          # GET  /api/state
│   ├── run_demo.py       # POST /api/run-demo
│   ├── run_custom.py     # POST /api/run-custom
│   ├── run_llm.py        # POST /api/run-llm
│   ├── run_batch.py      # POST /api/run-batch
│   ├── feedback.py       # POST /api/feedback
│   ├── create_task.py    # POST /api/create-task
│   ├── submit_output.py  # POST /api/submit-output
│   ├── evaluate_task.py  # POST /api/evaluate-task
│   ├── runs.py           # GET  /api/runs
│   └── reset.py          # POST /api/reset
├── core/                 # Pure Python engine (zero web dependencies)
│   ├── models.py         # Data models (AgentProfile, Task, Candidate, etc.)
│   ├── scoring.py        # ScoringEngine (relevancy + trust score)
│   ├── store.py          # ReputationStore (MemoryStore + RedisStore)
│   ├── controller.py     # TrustController (8-phase evaluation loop)
│   ├── config.py         # Scoring config loader
│   ├── llm.py            # Multi-provider LLM integration
│   └── fixtures.py       # Demo task + seed profiles loader
├── data/                 # Read-only fixture files
│   ├── demo_task.json
│   ├── seed_profiles.json
│   ├── scenarios.json
│   ├── task_healthcare.json
│   ├── task_finance.json
│   └── task_cybersecurity.json
├── config/
│   └── scoring.json      # Scoring weights (0.6 / 0.4)
├── public/               # Static frontend (vanilla JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tests/                # pytest suite (130+ tests)
├── requirements.txt
├── vercel.json
└── README.md
```

## How to Run Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

Tests use `MemoryStore` (in-memory) and do not require Redis or any external service.

## How to Deploy on Vercel

1. Push to GitHub
2. Import project in Vercel
3. Add a Vercel KV (Upstash Redis) store from the Vercel dashboard
4. Environment variables are auto-configured (`KV_REST_API_URL`, `KV_REST_API_TOKEN`)
5. Optional: set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY` for LLM evaluation
6. Deploy

## Current Scope Boundaries

- Keyword-based relevancy (no semantic/embedding scoring)
- Winner-only reputation updates (losers not penalized)
- Structural outcome validation (word count ≥ 3)
- No authentication or authorization
- 3 seed agents: GPT-4, Claude, LLaMA
