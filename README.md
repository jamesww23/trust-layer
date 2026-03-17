# Trust Layer

Reputation-based decision system for AI agents.

## What It Is

Trust Layer is a decision engine that sits between AI generation and execution. It does **not** generate outputs. It evaluates candidate outputs from multiple agents, computes a Trust Score for each, selects the best candidate, and persistently updates agent reputation.

**Core loop:** load task → load reputation → score → rank → select → update → persist

## What the MVP Demonstrates

- End-to-end agentic evaluation loop running locally
- Whole-word keyword relevancy scoring (no substring false positives)
- Weighted Trust Score formula: `0.6 * reputation + 0.4 * relevancy`
- Deterministic winner selection with tie-breaking
- Persistent reputation that evolves across runs
- Structured log output showing every step of the decision process
- All candidate outputs are pre-supplied strings — no LLM API calls

## Folder Structure

```
/src
  main.py           # CLI entry point
  controller.py     # TrustController — orchestrates the 11-step loop
  scoring.py        # ScoringEngine — relevancy + trust score
  store.py          # ReputationStore — JSON file persistence
  models.py         # Data models (AgentProfile, Task, Candidate, etc.)
  utils.py          # Config loading + structured logger
/data
  demo_task.json    # Fixture: task + candidates + seed profiles
  reputation.json   # Persistent agent reputation (updated each run)
/config
  scoring.json      # Weight configuration
/tests
  test_scoring.py   # Relevancy + trust score tests
  test_store.py     # Persistence tests
  test_controller.py # Full loop, tie-break, validation tests
```

## How to Run

```bash
python src/main.py
```

Run it again — the second run loads updated reputation from the first:

```bash
python src/main.py
```

## How to Run Tests

```bash
python -m pytest tests/ -v
```

Or without pytest:

```bash
python -m unittest discover tests -v
```

## What Is Intentionally Out of Scope

- Web UI / dashboard / frontend of any kind
- LLM API calls (candidates are pre-supplied fixtures)
- Embedding-based relevancy (Phase 2)
- Latency / cost scoring (Phase 2+)
- Loser reputation updates (Phase 2)
- Multi-user concurrency
- Production database backend
- Task history persistence
- User rating input
