# Agentic Reputation Infrastructure Layer — Team 8
**MAS.664 AI Studio, MIT SFMBA 2026**
**Team: Rachmawaty Sudirman | James Wu | Myint Htay Win**

---

## Project Overview

A shared, reusable reputation infrastructure layer for multi-agent ecosystems.
Agents register, discover each other, delegate tasks, and earn trust through
verified outcomes — not self-assertion.

Live site: https://trust-layer-topaz.vercel.app
GitHub: https://github.com/jamesww23/trust-layer

---

## Trust Score Formula (Team-Agreed)

This is the canonical formula the team agreed on in Assignment 5.
**All changes to trust scoring must follow this spec.**

```
trust = 0.35 × TSR  +  0.40 × FS  +  0.15 × RH  +  0.10 × SS
```

| Weight | Signal | Full Name | Definition |
|--------|--------|-----------|------------|
| 35% | TSR | Task Success Rate | `tasks_completed / tasks_received` |
| 40% | FS | Feedback Score | Weighted avg rating, weighted by requester's trust score |
| 15% | RH | Reliability History | `1 - std(last_10_ratings)` — consistency over time |
| 10% | SS | Specialization Score | Keyword overlap between tasks received and agent's skill_md |

### Constraints
- New agents start at **20% trust (prior)**
- Trust gate blocks delegation below **30%**
- Agents with `tasks_completed < 3` are capped at **40% max trust**
  (prevents buying trust through ratings alone)
- FS is requester-trust-weighted — a rating from a 20% agent counts
  less than one from an 80% agent (built-in manipulation resistance)

### Formula location in code
→ `core/scoring.py` — `compute_trust_score()`
→ `core/controller.py` — calls scoring on every feedback submission
→ `core/models.py` — `AgentProfile` stores: `tasks_received`,
  `tasks_completed`, `ratings`, `rating_weights`, `task_keywords`

---

## Anti-Manipulation Rules

These are non-negotiable guards. Do not remove them.

| Rule | What it prevents |
|------|-----------------|
| Max 3 ratings per (requester, provider) pair per 24h | Spam rating |
| `tasks_completed < 3` → trust capped at 40% | Bootstrapping via fake ratings |
| FS weighted by requester trust | Sybil / fake account inflation |
| Vouch limit: 1 vouch per target agent | Vouch flooding |
| Voucher accountability: if vouched agent drops below 25%, voucher loses 5% | Reckless vouching |

---

## Architecture: 7-Step Flow

```
Register → Discover → Trust Gate → Delegate → Execute → Feedback → Trust Update
```

1. **Register** — Agent self-describes with skill_md (markdown capabilities doc)
2. **Discover** — Multi-keyword search against skill_md + agent_name
3. **Trust Gate** — Blocks providers below 30% trust
4. **Delegate** — Requester posts task with payload to provider's inbox
5. **Execute** — Provider polls /api/tasks, runs capability, submits result
6. **Feedback** — Requester rates 0.0–1.0; rating is weighted by requester trust
7. **Trust Update** — 4-signal formula recalculates provider trust score

---

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | Local dev server (port 4000) |
| `core/store.py` | MemoryStore (local) + RedisStore (Vercel) |
| `core/controller.py` | Trust gate, delegation, vouch, simulation |
| `core/scoring.py` | **Trust formula lives here** |
| `core/models.py` | AgentProfile, Task data models |
| `api/*.py` | Vercel serverless endpoints |
| `public/index.html` | UI: Agents, Register, Find & Rate, Tasks, Activity, Simulate |
| `public/app.js` | Frontend logic |
| `skinscan_service.py` | SkinScanAgent (local, Logistic Regression + SMOTE) |
| `skinscan_service_cloud.py` | All 3 ML variants (Railway deployment, MODEL_TYPE env var) |
| `wisdom_request.py` | WisdomAgent requester demo |
| `analyze_image.py` | Real image → 8x8 grayscale → SkinScanAgent pipeline |
| `experiment_compare_models.py` | HW7 experiment: 3 models, trust evolution |
| `data/hmnist_8_8_L.csv` | HAM10000 dataset (8x8 grayscale, 10,015 images) |

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/register-agent` | Register a new agent |
| GET | `/api/discover?keyword=...` | Find agents by skill (multi-keyword) |
| GET | `/api/agents` | List all registered agents |
| POST | `/api/delegate-task` | Requester delegates task to provider |
| GET | `/api/tasks?agent_id=...` | Agent polls its inbox |
| POST | `/api/submit-result` | Provider submits completed result |
| POST | `/api/submit-feedback` | Requester rates provider (0.0–1.0) |
| POST | `/api/vouch` | Trusted agent vouches for new agent |
| GET | `/api/activity` | Full audit log of all task events |
| POST | `/api/run-simulation` | Run synthetic multi-round simulation |

---

## ML Models (SkinScanAgent Variants)

Deployed on Railway, all using HAM10000 dataset (8x8 grayscale, 15 engineered features).

| Agent ID | Agent Name | MODEL_TYPE | AUC | Melanoma Recall |
|----------|-----------|------------|-----|-----------------|
| `skinscan_agent` | SkinScanAgent | `logistic_smote` | 0.797 | ~49% |
| `skinscan_agent_2` | SkinScanAgent2 | `cart` | ~0.75 | low |
| `skinscan_agent_3` | SkinScanAgent3 | `cart_smote` | ~0.78 | high |

**HW7 Experiment result**: CART+SMOTE scored 100% accuracy across 6 rounds vs 50% for the other two.
The trust layer automatically routed reputation to the better-performing model.

### Feature engineering (15 features from 8×8 grayscale)
`mean_brightness, std_brightness, min_brightness, max_brightness, brightness_range,
vertical_asymmetry, horizontal_asymmetry, center_brightness, border_brightness,
center_border_diff, pixel_variance, edge_density, percentile_25, percentile_75, iqr`

---

## Deployment

| Component | Platform | URL |
|-----------|----------|-----|
| Trust Layer API + UI | Vercel | https://trust-layer-topaz.vercel.app |
| SkinScanAgent (LR+SMOTE) | Railway | Service 1 |
| SkinScanAgent2 (CART) | Railway | Service 2 |
| SkinScanAgent3 (CART+SMOTE) | Railway | Service 3 |

### Railway env vars (per service)
```
MODEL_TYPE       = logistic_smote | cart | cart_smote
AGENT_ID         = skinscan_agent | skinscan_agent_2 | skinscan_agent_3
AGENT_NAME       = SkinScanAgent  | SkinScanAgent2   | SkinScanAgent3
TRUST_LAYER_URL  = https://trust-layer-topaz.vercel.app
```

---

## Design Decisions (Do Not Change Without Team Discussion)

1. **Trust formula weights** (0.35/0.40/0.15/0.10) — agreed in Assignment 5 report
2. **30% trust gate** — below this, agents are blocked from receiving delegations
3. **20% prior** — all new agents start here, must earn trust through real work
4. **Requester-weighted FS** — security is built into the feedback score, not a separate layer
5. **No cost signal in MVP** — Cost/latency are tracked but not in the trust formula yet
6. **RedisStore for Vercel** — serverless requires external state; Redis KV via Upstash
7. **8×8 grayscale for ML** — matches HAM10000 hmnist format; real images preprocessed via PIL

---

## Running Locally

```bash
# Start trust layer server
cd trust-layer-git
python3 server.py 4000

# Start SkinScanAgent (Terminal 2)
python3 skinscan_service.py http://localhost:4000

# Run WisdomAgent request
python3 wisdom_request.py --case melanoma

# Analyze a real image
python3 analyze_image.py ~/Downloads/lesion.png --server http://localhost:4000

# Run HW7 experiment (against live site)
python3 experiment_compare_models.py --server https://trust-layer-topaz.vercel.app --rounds 6
```
