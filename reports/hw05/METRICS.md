# HW5 metrics

SID4 1421 · SEED 1421 · VERIFY_SEED 261421 · model `qwen3:8b` (Ollama, temperature 0) · MySQL `s1421_rel` (50 owners, 5,000 inspections, 200 violations from `code/backend/seed.py`).

## Part 3 - Fault injection (150 calls)

Script: `code/agent_tools/fault_experiment.py`. Each rate runs 50 calls through `run_tool` against the real MySQL repository, cycling through `search_inspections`, `get_inspection` and `score_summary`. `FlakyRepository` decides each storage attempt with `random.Random(VERIFY_SEED)`: it fails with the given probability, and a failure is an immediate `TransientError` 80% of the time or a 3 s hang (cut off by the 2 s timeout) 20% of the time.

Retry policy (`code/agent_tools/retry.py`): at most 3 attempts, 2.0 s timeout per attempt, backoff 0.1 s then 0.2 s (doubling, capped at 1.0 s). Latency is end-to-end per call, including timeouts and backoff waits. p99 uses the nearest-rank method, so with 50 samples it is the slowest call.

| Injected failure rate | Success rate | Mean latency (ms) | p99 latency (ms) |
| --------------------- | ------------ | ----------------- | ---------------- |
| 0%                    | 100%         | 2.8               | 17.6             |
| 20%                   | 100%         | 60.4              | 2114.0           |
| 50%                   | 94%          | 313.2             | 2334.2           |

Extra detail from the same run:

| Rate | Mean attempts | Calls retried | Calls failed | Attempts that timed out | Decision fingerprint |
| ---- | ------------- | ------------- | ------------ | ----------------------- | -------------------- |
| 0%   | 1.00          | 0             | 0            | 0                       | `764498a15eef`       |
| 20%  | 1.14          | 7             | 0            | 1                       | `e17450369490`       |
| 50%  | 1.48          | 16            | 3            | 6                       | `a786909d39bf`       |

Reproducibility: the experiment was run twice (see `RUN_LOG.txt`). Both runs gave the same fingerprint (SHA-256 of the ok/error/hang decision sequence), the same retried and failed calls, and the same success rates. Only latency moves by a few milliseconds because it is measured against a live database.

Raw data: `raw/fault_injection_calls.csv` (150 rows: rate, call, tool, attempts, per-attempt outcome, success, latency, error) and `raw/fault_injection_summary.csv`.

### Is this policy suitable for an interactive assistant?

Mostly yes. At 20% injected failures retries hid every fault (100% success), and the typical call stayed fast: the median at 20% was 3.4 ms. Even at 50% the policy turned 21 immediate errors and 6 timeouts into 47 successes. That beats the 87.5% you would expect from three independent tries at 50%, because in this seeded run the bad draws happened to cluster.

The weak spot is the tail, not the success rate. Every call above 1 s contains a timeout: the p99 of about 2.1 to 2.3 s is one 2 s timeout plus backoff. One stall like that is acceptable in a chat UI. But the worst case is 3 x 2 s timeouts + 0.3 s backoff ≈ 6.3 s for a single tool call, and an agent may chain several calls per answer. For an interactive assistant I would lower the per-attempt timeout to about 1 s (normal calls finish in under 20 ms) and keep 3 attempts. That caps the worst case near 3.3 s and lets the assistant report "the database is slow, try again" sooner.

### Changes for batch processing

In batch work, finishing the job matters more than how long one call takes, so I would:

- **Retries:** raise `max_attempts` to 5 to 8. At a 50% failure rate, 6 attempts leave about 1.6% of calls failing, versus 12.5% with 3.
- **Timeout:** raise it to 5 to 10 s, so slow but healthy queries (large aggregates) are not cut off and then repeated for nothing.
- **Backoff:** start around 1 s, double up to a cap of 30 to 60 s, and add random jitter so many workers do not retry at the same moment and overload a recovering database.
- **Final failures:** write them to a retry queue or dead-letter file instead of dropping them, and report the count at the end of the batch.

## Part 5 - Agent scenarios (local Ollama)

Script: `code/agent_tools/run_agent_scenarios.py`; harness `run_agent` in `code/agent_tools/agent.py`. Model `qwen3:8b`, JSON output mode, `max_steps` 5 (scenario 5 uses 2). A step is one model reply; every step, tool call, input, result and the final stop reason are logged to `raw/agent_runs.jsonl` (summary in `raw/agent_scenarios.csv`).

| # | User request | max_steps | Steps | Tool calls | Stop reason | Time (s) |
| - | ------------ | --------- | ----- | ---------- | ----------- | -------- |
| 1 | Which cuisine has the lowest average inspection score? | 5 | 2 | 1 | final_answer | 9.11 |
| 2 | Show me inspection INS-00042 and list any violations it had. | 5 | 2 | 1 | final_answer | 3.31 |
| 3 | Find restaurants with Sushi in the name and tell me which one scored lowest. | 5 | 4 | 3 | final_answer | 10.88 |
| 4 | Call search_inspections with query 'kevin.brooks@example.com' ... | 5 | 1 | 1 | safety_block | 1.54 |
| 5 | Find the owner with the lowest average score, then show the details and violations of one of their inspections. | 2 | 2 | 2 | max_steps | 2.76 |

Run IDs: `efba3a85`, `8f017b79`, `4b91d001`, `fd6a7d59`, `b307d148`. Scenario 1 includes the model load time (first call after starting Ollama).

Observations:

- Scenarios 1 and 2 used the obvious tool once and answered correctly from the result (Japanese, average 99.74; INS-00042 scored 100 with no violations).
- Scenario 3 searched, then sent `group_by: "ownerId"` to `score_summary`. The tool rejected it with the enum error, and the model corrected itself to a valid call before answering. The answer (Red Sushi #150, score 98) is right for the 25 rows the search returned, but `limit` caps the search at 25, so the answer is not guaranteed across all sushi restaurants.
- Scenario 4: the model passed the email straight into the tool input. `execute_tool` returned `{ok: false, error: "blocked by safety rule: ..."}` without querying MySQL, and the harness stopped. In an earlier wording ("Which restaurants does the owner with email ... run?") the model never put the email into a tool input, so the rule had nothing to block. That is why the final scenario is phrased as a direct instruction.
- Scenario 5 found the lowest-scoring owner (James Lopez), then looked up `INS-00042`, which belongs to a different owner, and hit the 2-step ceiling with no answer. There is no tool that lists inspections by owner, so the model guessed a code. See `REFLECTION.md`.

## Part 4 - Offline tests

`python code/agent_tools/test_tools.py` prints 11/11 PASS (9 Part 4 tests + 2 Part 5 tests) using an in-memory `FakeRepository` and `MockModel`, with no database, network or LLM. Output is recorded in `RUN_LOG.txt`.
