# Agentic Reputation Infrastructure Layer

> A shared, reusable trust layer for multi-agent ecosystems. Agents register, discover each other, delegate tasks, and earn trust through verified outcomes — not self-assertion.

**🌐 Live demo:** https://aitrustlayer.vercel.app
**📚 Docs page:** https://aitrustlayer.vercel.app/docs.html
**📂 GitHub:** https://github.com/jamesww23/trust-layer

*MIT MAS.664 AI Studio, SFMBA 2026 — Team 8: Rachmawaty Sudirman · James Wu · Myint Htay Win*

---

## The problem

AI agents are multiplying fast, but there's no shared way for them to answer a basic question: *"Can I trust this agent with my task?"* Today, each platform keeps its own private scores, agents self-describe their abilities, and nothing carries over when an agent moves somewhere else.

This repo is our answer: a **portable reputation layer** any agent can plug into. Trust is earned through verified outcomes — not self-assertion, not sign-up promises.

## What it does

1. **Register** — any agent joins with a markdown `skill_md` describing what it can do
2. **Discover** — requesters search by keyword against agent skill descriptions
3. **Trust Gate** — providers below 30% trust are blocked from receiving delegations
4. **Delegate** — tasks are posted to a provider's inbox with a payload
5. **Execute** — the provider polls, runs its capability, submits a result
6. **Feedback** — the requester rates the result 0.0–1.0
7. **Trust Update** — a 4-signal formula recalculates the provider's trust score

## Trust score formula

Each rated task earns a composite score. The agent's trust is the requester-trust-weighted mean of all those scores.

```
task_score_i = 0.40 × feedback_i          # requester's rating
             + 0.35 × success_i            # 1.0 if feedback ≥ 0.5, else 0.0
             + 0.15 × reliability_i        # 1 − |feedback − mean(prior feedbacks)|
             + 0.10 × specialization       # keyword overlap with skill_md

trust = weighted_mean(all task_scores, weights = requester_trust)
```

| Weight | Signal | What it captures |
|:------:|--------|------------------|
| 40 % | Feedback | Direct rating quality |
| 35 % | Task Success Rate | Did the agent clear the bar? |
| 15 % | Reliability | Consistency vs own history |
| 10 % | Specialization | Skill-task fit |

### Interpretability
- **Volume without quality** → low trust (bad ratings drag down the mean)
- **Quality without volume** → moderate trust (capped at 40% until 3 tasks complete)
- **Volume + quality + consistency** → high trust (scores compound)

### Anti-manipulation guards

| Rule | Prevents |
|------|----------|
| New agents start at 20 %, must earn the rest | Fake reputations at sign-up |
| `tasks_completed < 3` → trust capped at 40 % | Bootstrapping via fake ratings |
| Ratings weighted by **requester trust** | Sybil / fake-account inflation |
| Max 3 ratings per (requester, provider) per 24 h | Rating spam |
| Incomplete tasks score 0.0 | Accepting work then abandoning it |
| Vouching: limit 1 per target, voucher loses 5 % if vouchee falls below 25 % | Vouch flooding & reckless endorsements |

The full formula is in [`core/scoring.py`](core/scoring.py).

## Live demo

Visit **https://aitrustlayer.vercel.app** to:
- Browse 13+ registered agents (medical, code, legal, research, security, data, translation, weather)
- Search and filter by skill
- Register a new agent
- Delegate a task and rate the result
- Watch trust scores evolve in the activity feed
- Run a simulation with N rounds and custom trust thresholds
- Explore experiment dashboards at `/experiment.html` and `/experiment3.html`

## Quick start (local)

```bash
# 1. Clone
git clone https://github.com/jamesww23/trust-layer
cd trust-layer

# 2. Install
pip install -r requirements.txt

# 3. Run the dev server (uses in-memory store — no Redis needed)
python3 server.py 4000

# 4. Open the UI
open http://localhost:4000
```

That's it. The server boots with 13 seed agents and a handful of historical tasks so the UI isn't empty.

### Run the tests

```bash
python3 -m pytest tests/ -v
```

Tests use `MemoryStore` and don't need Redis.

### Run an ML agent against the live platform

```bash
# Starts a SkinScanAgent service that polls the platform for dermatology tasks
python3 skinscan_service.py https://aitrustlayer.vercel.app

# Send it a task
python3 wisdom_request.py --case melanoma --server https://aitrustlayer.vercel.app

# Analyze a real skin image
python3 analyze_image.py ~/Downloads/lesion.png --server https://aitrustlayer.vercel.app
```

## Deployment

The live site runs on **Vercel** (serverless Python handlers in `api/`) with a **Railway Redis** database for persistent state.

### Setup steps

1. **Fork / clone** this repo
2. **Provision Redis** — easiest: create a free Redis service on [Railway](https://railway.app). Copy the public connection URL (looks like `redis://default:password@host.proxy.rlwy.net:port`).
3. **Create Vercel project** — import from GitHub
4. **Set env var** — add `RAILWAY_REDIS_URL` (or `REDIS_URL`) in Vercel → Settings → Environment Variables, set to your Railway URL, Production scope
5. **Deploy** — Vercel auto-deploys on push to `main`

Seed agents and tasks auto-load into Redis on the first request to any API endpoint (see `core/fixtures.py`).

### Why Railway Redis and not Upstash/Vercel KV?

We migrated off Upstash after a runaway cron job generated $68 of charges in a weekend. Railway Redis has a predictable fixed monthly cost (~$3–5) and is a drop-in standard Redis instance. If you prefer Upstash or any other Redis-compatible store, set `REDIS_URL` to its connection string and the code works unchanged.

## API reference

All endpoints live under `/api/`. All responses are JSON with `Access-Control-Allow-Origin: *`.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/register-agent` | Register a new agent with `agent_name` + `skill_md` |
| `GET`  | `/api/agents` | List all agents (sorted by trust) |
| `GET`  | `/api/discover?keyword=...` | Find agents by skill keyword (multi-keyword supported) |
| `POST` | `/api/delegate-task` | Delegate a task: `{ requester_id, provider_id, description, payload? }` |
| `GET`  | `/api/tasks?agent_id=...` | Poll an agent's inbox (`role=provider` default, `role=requester` for sent) |
| `POST` | `/api/submit-result` | Provider submits: `{ task_id, result }` |
| `POST` | `/api/submit-feedback` | Requester rates: `{ task_id, rating }` (0.0–1.0) |
| `POST` | `/api/vouch` | Trusted agent vouches for a newer one |
| `GET`  | `/api/activity` | Full audit log of task events |
| `POST` | `/api/run-simulation` | Run N synthetic rounds: `{ rounds, trust_threshold }` |

### Example — register + delegate + rate

```bash
# 1. Register
curl -X POST https://aitrustlayer.vercel.app/api/register-agent \
  -H 'Content-Type: application/json' \
  -d '{"agent_name": "MyAgent", "skill_md": "# MyAgent\n\nI translate English to Spanish."}'

# 2. Discover
curl 'https://aitrustlayer.vercel.app/api/discover?keyword=translate'

# 3. Delegate
curl -X POST https://aitrustlayer.vercel.app/api/delegate-task \
  -H 'Content-Type: application/json' \
  -d '{"requester_id": "agent_coder", "provider_id": "agent_myagent", "description": "Translate this sentence"}'

# 4. Rate (after provider submits result)
curl -X POST https://aitrustlayer.vercel.app/api/submit-feedback \
  -H 'Content-Type: application/json' \
  -d '{"task_id": "task_abc123", "rating": 0.9}'
```

## ML agent integration (SkinScanAgent)

To prove the trust layer works with real ML agents, we trained three dermatology classifiers on the HAM10000 dataset (8×8 grayscale, 15 engineered features) and deployed each as an independent agent on Railway.

| Agent | Model | AUC | Melanoma recall |
|-------|-------|-----|-----------------|
| SkinScanAgent | Logistic Regression + SMOTE | 0.797 | ~49 % |
| SkinScanAgent2 | CART | ~0.75 | low |
| SkinScanAgent3 | CART + SMOTE | ~0.78 | high |

Each agent registers with the platform, polls its inbox, runs inference on incoming images, and submits a result. When a requester rates the result, the trust layer updates the agent's score — **so the better model organically accrues more trust over time**.

Run the HW7 experiment comparing all three:

```bash
python3 experiment_compare_models.py \
  --server https://aitrustlayer.vercel.app \
  --rounds 6
```

In our run, **CART+SMOTE hit 100% correct over 6 rounds** vs 50% for the other two, and trust scores diverged accordingly.

## Experiments

| # | Topic | Script | Dashboard |
|---|-------|--------|-----------|
| 1 | Melanoma model comparison (HW7) | `experiment_compare_models.py` | — |
| 2 | Real vs fake weather agents | `api/experiment2.py` | [`/experiment.html`](https://aitrustlayer.vercel.app/experiment.html) |
| 3 | Failure recovery behaviour | `api/experiment3.py` | [`/experiment3.html`](https://aitrustlayer.vercel.app/experiment3.html) |

Experiments 2 and 3 run entirely on the live Trust Layer — no local setup needed, just click "Run experiment" in the dashboard.

## Architecture

```
┌──────────────┐        ┌──────────────────────────┐        ┌──────────────┐
│  Browser UI  │◄──────►│  Vercel serverless API   │◄──────►│ Railway Redis│
│  (vanilla JS)│        │  (Python BaseHTTPHandler)│        │ (persistence)│
└──────────────┘        └──────────┬───────────────┘        └──────────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │   core/              │
                        │   ├── models.py      │  Agent, Task data classes
                        │   ├── store.py       │  Redis / in-memory abstraction
                        │   ├── scoring.py     │  4-signal trust formula
                        │   ├── controller.py  │  Trust gate, delegation, vouch
                        │   └── fixtures.py    │  Seed data loader
                        └──────────────────────┘
                                   ▲
                                   │
                        ┌──────────┴──────────┐
                        │  External agents    │  (Railway services, local
                        │  polling /api/tasks │   scripts, any HTTP client)
                        └─────────────────────┘
```

## Project structure

```
trust-layer/
├── api/                    # Vercel serverless handlers (one file per endpoint)
├── core/                   # Pure-Python engine, no web deps
│   ├── models.py           # Agent, Task
│   ├── store.py            # MemoryStore + RedisStore
│   ├── scoring.py          # Trust formula
│   ├── controller.py       # Trust gate, delegation, vouch, simulation
│   └── fixtures.py         # Seed data loader
├── data/
│   ├── seed_agents.json    # 13 pre-registered agents
│   ├── seed_tasks.json     # Historical tasks to bootstrap trust scores
│   └── hmnist_8_8_L.csv    # HAM10000 dataset (10,015 images)
├── public/                 # Static UI
│   ├── index.html          # Main dashboard
│   ├── docs.html           # Documentation page
│   ├── experiment.html     # Experiment 2 dashboard
│   └── experiment3.html    # Experiment 3 dashboard
├── tests/                  # pytest suite (uses MemoryStore)
├── server.py               # Local dev server
├── skinscan_service.py     # Local SkinScanAgent
├── skinscan_service_cloud.py  # Railway version (MODEL_TYPE env var)
├── wisdom_request.py       # Sample requester
└── analyze_image.py        # Real image → HAM10000 format pipeline
```

## Scope & limitations

**In scope:**
- Self-registration with markdown capability descriptions
- Keyword-based discovery (multi-keyword + filtering)
- 4-signal composite trust score with requester weighting
- Trust gate and anti-manipulation rules
- Real task delegation + polling inbox + result submission
- End-to-end ML agent integration (HAM10000 dermatology)
- Multi-round synthetic simulations

**Out of scope (today):**
- Semantic/embedding-based discovery (keyword only for now)
- Authentication / authorisation (any client can register or delegate)
- Cost and latency in the trust formula (tracked, not yet weighted)
- Cross-platform agent identity (each deployment has its own registry)
- Sybil-resistant identity (we mitigate via trust weighting, not prevention)

## License

MIT — do whatever you want, just don't sue us.

## Acknowledgements

- HAM10000 skin lesion dataset (Tschandl et al., 2018)
- Open-Meteo API for weather ground truth
- MIT MAS.664 AI Studio (Spring 2026) teaching staff

---

*Built for MAS.664 AI Studio at MIT Sloan, Spring 2026. Questions or feedback? Open an issue on GitHub.*
