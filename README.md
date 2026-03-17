# Trust Layer MVP

Reputation-based decision system for AI agents. Evaluates candidate outputs, computes Trust Scores, selects the best candidate, and persistently updates agent reputation.

Based on **Trust Layer PRD v2.1**.

## Quick Start

```bash
python main.py
```

Runs a single demo task using fixture data from `./data/demo_task.json`. No LLM API calls — all candidate outputs are pre-supplied strings.

## Project Structure

```
├── main.py                    # CLI entry point
├── config/
│   └── scoring.json           # Weight configuration (w_rep=0.6, w_rel=0.4)
├── data/
│   ├── demo_task.json         # Fixture: task + candidates + initial profiles
│   └── reputation.json        # Persisted agent profiles (created on first run)
├── trust_layer/
│   ├── schemas.py             # Data models (AgentProfile, Task, Candidate, etc.)
│   ├── scoring_engine.py      # Relevancy + Trust Score computation
│   ├── reputation_store.py    # JSON file backend for agent profiles
│   ├── controller.py          # 11-step agent loop orchestrator
│   └── logger.py              # Structured log output
└── tests/
    └── test_trust_layer.py    # 18 tests covering all PRD success criteria
```

## How It Works

1. Load task + candidates from fixture JSON
2. Load/initialize agent reputation profiles
3. Compute relevancy (whole-word keyword matching)
4. Compute Trust Score: `(0.6 * success_rate) + (0.4 * relevancy)`
5. Rank candidates with deterministic tie-breaking
6. Select winner, update reputation, persist state

## Running Tests

```bash
python -m unittest discover tests -v
```

## Configuration

Edit `config/scoring.json` to adjust weights:

```json
{
  "w_reputation": 0.6,
  "w_relevancy": 0.4
}
```

Weights must sum to 1.0 — validated at startup.
