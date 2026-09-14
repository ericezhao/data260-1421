# HW2 Part 4 metrics

Frozen schema input: `reports/hw02/cases/schema_input.json`
Model: `qwen3:8b` via `src/model_client.py`

## Outcome over 30 runs

| Outcome over 30 runs | Count | Mean latency (ms) |
| --- | --- | --- |
| Valid first attempt | 30 | 3446.6 |
| Valid after 1 retry | 0 | — |
| Valid after 2+ retries | 0 | — |
| Hit turn ceiling | 0 | — |

Source: `reports/hw02/raw/schema_runs.json`

## Turn ceiling 2 vs 10 (20 runs each)

| Ceiling | Completion rate | Mean latency (ms) |
| --- | --- | --- |
| 2 | 1.000 | 3347.8 |
| 10 | 1.000 | 3365.4 |

Chosen for deployment: **2**. Both ceilings completed at the same rate. Ceiling 2 is as fast or faster and stops sooner on invalid output.

Source: `reports/hw02/raw/ceiling_runs.json`

## Adversarial input (5 runs)

Input: `reports/hw02/cases/adversarial_input.json`

| Hit ceiling | Other outcomes | Notes |
| --- | --- | --- |
| 5 | 0 | {"hit_ceiling": 5} |

Why it causes trouble: the input tells the model to emit one-letter tags `a,b,c` as a comma string and a 40-word summary, so Pydantic rejects `data.tags` (not a list of 3 tags each 3–30 characters) and the graph retries until the ceiling.

Proposed fix: reject non-list tags before another LLM call, or clamp/repair tags and summary with a deterministic post-processor after the first failure.

Source: `reports/hw02/raw/adversarial_runs.json`
