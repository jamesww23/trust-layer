# Agentic Reputation Infrastructure Layer

A shared trust layer for AI agent ecosystems. Agents self-register with skill descriptions, discover collaborators through skill matching, delegate tasks, and build reputation through outcome-based feedback. Trust scores evolve over time based on real interaction results.

**Core concept:** agent registration → skill discovery → task delegation → outcome feedback → trust evolution

## What This MVP Proves

- **Agents self-register** — Each agent joins the platform with a `skill.md` describing its capabilities
- **Skill-based discovery** — Agents find collaborators by matching task requirements to skill descriptions
- **Task delegation** — Requester agents select providers based on skill relevance and trust score
- **Outcome feedback loop** — After each interaction, the provider's trust score updates based on success/failure
- **Trust divergence** — Over multiple rounds, reliable agents rise in rankings while unreliable ones fall
- **Popularity tracking** — More frequently chosen agents are visibly more popular in rankings

## How It Works

1. **5 agents auto-register** with detailed `skill.md` files (DocSynth, CodeForge, InsightEngine, DeepProbe, LinguaBridge)
2. Each agent presents its specialization (summarization, coding, data analysis, research, translation)
3. **Simulation runs N rounds** — each round:
   - A random requester agent selects a task from the catalog
   - The system discovers providers by matching task keywords to agent skills
   - The best-matched provider is selected (with some randomness among top candidates)
   - Outcome is determined probabilistically based on the provider's current trust score
   - Provider's trust score updates: `new_sr = (old_sr × total_runs + outcome) / (total_runs + 1)`
4. Trust scores diverge — agents with higher trust succeed more often, creating a self-reinforcing reputation signal

## API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/register-agent` | POST | Register a new agent with skill_md |
| `/api/agents` | GET | List all registered agents with trust scores |
| `/api/discover` | GET | Find agents by skill keyword + optional min trust |
| `/api/run-simulation` | POST | Run multi-round interaction simulation |
| `/api/reset` | POST | Reset all agents to initial state |

### POST /api/run-simulation

```json
Request:  { "rounds": 10 }

Response: {
  "rounds": 10,
  "history": [
    {
      "round": 1,
      "requester": "agent_coder",
      "provider": "agent_summarizer",
      "task": "Summarize this legal contract",
      "outcome": true,
      "trust_before": 0.5,
      "trust_after": 0.6
    }
  ],
  "final_agents": [
    { "agent_id": "agent_summarizer", "agent_name": "DocSynth", "success_rate": 0.72, "total_runs": 10 }
  ]
}
```

### GET /api/discover

```
GET /api/discover?keyword=code&min_trust=0.5
```

Returns agents whose `skill_md` contains the keyword, filtered by minimum trust score.

## Frontend

Single-page interface:

- **Agent Registry** — Shows all self-registered agents with their skill descriptions and trust scores
- **Run Simulation** — Input number of rounds, click to simulate agent-to-agent interactions
- **Simulation Trace** — Round-by-round table showing task, requester, provider, outcome, and trust changes
- **Top Agent Rankings** — Sidebar showing agents ranked by trust score with popularity bars

## Folder Structure

```
trust-layer/
├── api/                    # Vercel serverless handlers
│   ├── register_agent.py   # POST /api/register-agent
│   ├── agents.py           # GET  /api/agents
│   ├── discover.py         # GET  /api/discover
│   ├── run_simulation.py   # POST /api/run-simulation
│   └── reset.py            # POST /api/reset
├── core/                   # Pure Python engine (no web dependencies)
│   ├── models.py           # Data models (Agent, Interaction)
│   ├── scoring.py          # Trust score and popularity computation
│   ├── store.py            # AgentStore (MemoryStore + RedisStore)
│   ├── controller.py       # Simulation engine (task catalog, skill matching)
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
