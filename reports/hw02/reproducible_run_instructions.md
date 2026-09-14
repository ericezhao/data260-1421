# Reproducible Run Instructions — DATA-260 Homework 2

These instructions reproduce the Homework 2 FastAPI app, LangGraph run, Part 4 experiments, and smoke test from the repository root.

## Personal Configuration

- SID4: 1421
- PORT_BASE: 8521
- PREFIX: `s1421`
- SEED: 1421
- VERIFY_SEED: 261421
- DOMAIN_ID: 5
- Assigned domain: Local restaurant inspections
- Model: `qwen3:8b` via `src/model_client.py`

## 1. Start from the repository root

Run all commands below from the root of the repository.

## 2. Activate the Python environment

```bash
conda activate data260
```

## 3. Confirm the local Ollama model is available

```bash
ollama list
```

## 4. FastAPI app (Parts 1–2)

```bash
python code/main.py
```

Open [http://localhost:8521](http://localhost:8521). Preview states: `/?state=loading`, `/?state=empty`, `/?state=error`.

## 5. LangGraph (Part 3)

```bash
cd code
python -m restaurant_graph.workflow
```

This uses `.stream()` and `schema_only=False`, so Planner and Reviewer both run.

## 6. Schema and loop-safety experiments (Part 4)

Frozen input (saved before the runs):

```text
reports/hw02/cases/schema_input.json
```

Adversarial input:

```text
reports/hw02/cases/adversarial_input.json
```

```bash
python code/run_hw02_part4.py --experiment schema
python code/run_hw02_part4.py --experiment ceiling
python code/run_hw02_part4.py --experiment adversarial
```

Machine-readable results go to `reports/hw02/raw/`. The runner rewrites `reports/hw02/METRICS.md` from those JSON files.

## 7. Smoke test

```bash
python code/verify_hw02.py
```

This writes `reports/hw02/verification.json`. Re-run it after tagging `hw2` if you need the commit hash in that file to match the tagged commit.

## 8. Reproducibility artifacts

- `RUN_LOG.txt` — console rows from the Part 4 runs that produced the reported metrics, plus the smoke-test output
- `AI_USE.md` — answers to the four AI-use questions
- `cases/` — frozen schema and adversarial inputs
- `raw/` — schema, ceiling, and adversarial JSON
- `METRICS.md` — reported tables
- `verification.json` — Homework 2 smoke-test results
