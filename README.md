# Agentic Reputation Infrastructure Layer

A shared trust layer for AI agent ecosystems. Agents self-register with skill descriptions, discover collaborators through skill matching, delegate tasks, and build reputation through outcome-based feedback. Trust scores evolve over time based on real interaction results.

**Core flow:** Discovery → Trust Gate → Delegation → Outcome → Feedback → Registry Update

## What This MVP Proves

- **Agents self-register** — Each agent joins the platform with a `skill.md` describing its capabilities
- **Skill-based discovery** — Agents find collaborators by matching task requirements to skill descriptions
- **Trust gate** — Providers below a configurable trust threshold are rejected and flagged
- **Task delegation** — Requester agents select providers based on skill relevance and trust score
- **Outcome feedback loop** — After each interaction, the requester submits explicit feedback
- **Trust divergence** — Over multiple rounds, reliable agents rise in rankings while unreliable ones fall
- **Popularity tracking** — More frequently chosen agents are visibly more popular in rankings
- **Rejection tracking** — Agents that fail the trust gate are flagged, visible in rankings

## 6 Architecture Components

### 1. Discovery API
Find agents by skill keyword match. Agents whose `skill_md` contains matching keywords are returned as candidates, sorted by relevance (keyword occurrence count) first, then by trust score.

### 2. Reputation Registry
Each agent maintains: `success_rate` (trust score), `total_runs` (interaction count), `flagged` (rejection count), `skill_md` (capabilities), and timestamps. Trust updates use the feedback score (not the raw binary outcome): `new_sr = (old_sr × total_runs + feedback_score) / (total_runs + 1)`.

### 3. Trust Gate
Before delegation, candidates pass through a configurable trust threshold (default: 0.3). Agents below the threshold are rejected and their `flagged` count increments. If all candidates are rejected, the round is skipped.

### 4. Feedback Ingestion
After each interaction, the requester submits an explicit feedback score (0.0–1.0). Feedback is influenced by outcome and provider trust. A standalone `/api/submit-feedback` endpoint also accepts external feedback.

### 5. Task Delegation
The requester selects a provider from trust-gate-passed candidates. Selection favors the top skill-matched agents with some randomness among the top 2.

### 6. Outcome Flow
Task is executed → outcome determined probabilistically based on provider trust → requester submits feedback score (0.0–1.0) reflecting satisfaction → feedback score is fed into the trust update formula → changes persisted to registry. The standalone `/api/submit-feedback` endpoint uses the same trust update path.

## How It Works

1. **5 agents auto-register** with detailed `skill.md` files (DocSynth, CodeForge, InsightEngine, DeepProbe, LinguaBridge)
2. Each agent presents its specialization (summarization, coding, data analysis, research, translation)
3. **Simulation runs N rounds** — each round:
   - A random requester agent selects a task from the catalog
   - **Discovery**: The system finds providers by matching task keywords to agent skills
   - **Trust Gate**: Candidates below the threshold are rejected and flagged
   - **Delegation**: Best-matched provider is selected from gate-passed candidates
   - **Outcome**: Determined probabilistically based on provider's trust score
   - **Feedback**: Requester submits explicit feedback score (0.0–1.0)
   - **Registry Update**: Feedback score is fed into `(old × runs + feedback) / (runs + 1)` and persisted
4. Trust scores diverge — agents with higher trust succeed more often, creating a self-reinforcing reputation signal

## API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/register-agent` | POST | Register a new agent with skill_md |
| `/api/agents` | GET | List all registered agents with trust scores |
| `/api/discover` | GET | Find agents by skill keyword + optional min trust |
| `/api/run-simulation` | POST | Run multi-round interaction simulation |
| `/api/submit-feedback` | POST | Submit explicit feedback for an agent |
| `/api/reset` | POST | Reset all agents to initial state |

### POST /api/run-simulation

```json
Request:  { "rounds": 10, "trust_threshold": 0.3 }

Response: {
  "rounds": 10,
  "trust_threshold": 0.3,
  "history": [
    {
      "round": 1,
      "requester": "agent_coder",
      "provider": "agent_summarizer",
      "task": "Summarize this legal contract",
      "discovery_candidates": 3,
      "gate_passed": true,
      "gate_rejected": [],
      "outcome": true,
      "feedback_score": 0.85,
      "trust_before": 0.5,
      "trust_after": 0.6
    }
  ],
  "final_agents": [
    { "agent_id": "agent_summarizer", "agent_name": "DocSynth", "success_rate": 0.72, "total_runs": 10, "flagged": 0 }
  ]
}
```

### POST /api/submit-feedback

```json
Request:  { "agent_id": "agent_summarizer", "score": 0.85 }

Response: {
  "status": "feedback_recorded",
  "agent": { "agent_id": "agent_summarizer", "success_rate": 0.735, ... }
}
```

### GET /api/discover

```
GET /api/discover?keyword=code&min_trust=0.5
```

Returns agents whose `skill_md` contains the keyword, filtered by minimum trust score.

## Frontend

Single-page interface showing the full 6-component architecture:

- **Architecture Flow** — Visual pipeline: Discovery → Trust Gate → Delegation → Outcome → Feedback → Registry Update
- **Agent Registry** — Shows all self-registered agents with their skill descriptions, trust scores, and flagged counts
- **Run Simulation** — Configure rounds and trust gate threshold, then simulate agent-to-agent interactions
- **Simulation Trace** — Round-by-round table showing task, requester, provider, gate status, outcome, feedback score, and trust changes
- **Top Agent Rankings** — Sidebar showing agents ranked by trust score with popularity bars and flagged counts

## Folder Structure

```
trust-layer/
├── api/                    # Vercel serverless handlers
│   ├── register_agent.py   # POST /api/register-agent
│   ├── agents.py           # GET  /api/agents
│   ├── discover.py         # GET  /api/discover
│   ├── run_simulation.py   # POST /api/run-simulation
│   ├── submit_feedback.py  # POST /api/submit-feedback
│   └── reset.py            # POST /api/reset
├── core/                   # Pure Python engine (no web dependencies)
│   ├── models.py           # Data models (Agent with flagged, Interaction with gate/feedback)
│   ├── scoring.py          # Trust score and popularity computation
│   ├── store.py            # AgentStore (MemoryStore + RedisStore)
│   ├── controller.py       # Simulation engine (6 components: discovery, gate, delegation, outcome, feedback, registry)
│   └── fixtures.py         # Seed agent loader
├── data/
│   └── seed_agents.json    # 5 pre-registered agents with skill_md
├── public/                 # Static frontend (vanilla HTML/CSS/JS)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── tests/                  # pytest suite
│   ├── test_models.py
│   ├── test_store.py
│   ├── test_simulation.py
│   └── test_fixtures.py
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
5. Deploy

## Scope Boundaries

**In scope:**
- Agent self-registration with skill descriptions
- Skill-based discovery (substring matching)
- Trust gate with configurable threshold
- Explicit feedback ingestion (separate step)
- Rejection tracking and flagging
- Simulated task delegation and outcome feedback
- Trust score evolution over multiple rounds
- Popularity tracking (interaction frequency)

**Out of scope:**
- Real agent-to-agent communication
- Async execution or background workers
- Semantic/embedding search
- Latency, cost, or bandwidth signals
- Authentication or authorization
- Production-scale infrastructure

## Team

MIT MAS.664 AI Studio — Team 8
- Rachmawaty Sudirman
- James Wu
- Myint Htay Win
