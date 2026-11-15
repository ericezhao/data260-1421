# METRICS - HW10

SID4 1421 · PREFIX s1421 · restaurant inspections  
Builds on HW8 Kafka Planner–Writer–Reviewer (`correlation_id`) and HW9 Redis semantic cache.

## Part 1 - Streamlit ops dashboard

App: `code/hw10/app.py`  
Run: `PYTHONPATH=".:code:.deps" streamlit run code/hw10/app.py --server.port 8521`

Pages: **Summary** (request count, cache hit/miss, error rate, e2e latency, time window + data sources), **Evaluation** (Part2 stage scores + Part3 Spearman/MAE/repeatability + short coordination read), **Trace lookup** (`trace_id` = `correlation_id`, stage order, hit vs miss path).

Uses `@st.cache_resource` for `SpanStore` and `@st.cache_data` for JSON/tables.

Data sources: `reports/hw10/raw/spans/`, `raw/messages/`, `raw/eval/`, `raw/judge_metrics.json`, `raw/latency_50_miss.json`.

## Part 2 - Automated evaluation (GEval / DeepEval)

Join key: `correlation_id` (= `trace_id`). Artifacts under `raw/messages/<id>.json` keep plan / draft / final + metadata.

Local judge: **Ollama `qwen3:8b`** (`think:false`), GEval-style rubrics, 1–5 scale, timeout `HW10_JUDGE_TIMEOUT` (default 60s).  
DeepEval GEval smoke: `raw/deepeval_smoke.json` (engine `deepeval_geval_ollama`, score 5 on a short writer sample).

Example e2e question: *Why do sushi restaurants care about health inspection scores (0-100)?*  
`trace_id=part2-d75168393967`

| Criterion | Score (1–5) | Note |
| --- | ---: | --- |
| Plan Quality | 5 | Numbered plan, did not answer the question |
| Writer Helpfulness | 5 | Concrete sushi / food-safety draft |
| Final Answer Helpfulness | 5 | Final still helpful |
| Final-vs-Draft | **3** | **draft == final** (Reviewer approved with no edits) |

Coordination: Planner and Writer worked; Reviewer did not improve the draft on this run — reported as-is, not forced positive. Diff = 0.

## Part 3 - Validate the judge

Frozen before judge (commit `75f93af`):  
- `code/hw10/data/eval_cases.json` — 20 Writer drafts  
- `code/hw10/data/human_labels.csv` — hand labels 1–5  

Judge: `qwen3:8b`, temperature 0, 3 repeats on the same 20 drafts.

| Metric | Value |
| --- | ---: |
| Spearman ρ (human vs judge run1) | 0.390 |
| MAE | 0.70 |
| Cases with any score change across 3× | 0 / 20 |
| Mean abs change | 0.0 |
| Max abs change | 0.0 |

Raw pairs: `reports/hw10/raw/judge_metrics.json`.

Would I trust this judge to gate a deploy? **No.** Spearman is only moderate, the model is slightly optimistic vs my labels on mid-quality drafts, and I would want a holdout set + calibrated thresholds before gating.

## Part 4 - Tracing and latency

`trace_id` reused from HW8 `correlation_id`. Spans JSONL: `raw/spans/<trace_id>.jsonl` with stage, start, end, duration_ms, status, error.

Named traces (also in `raw/trace_index.json` / `raw/part4_named_traces.json`):

| Label | trace_id | Notes |
| --- | --- | --- |
| cache-hit | `hit-0df6163fe1` | only `cache_lookup` (hit) |
| cache-miss success | `miss-246adb0763` | lookup → planner → writer → reviewer → eval |
| failed | `fail-04187a3d70` | fails at **writer**: `RuntimeError: injected writer failure` |

### 4.3 Stage-latency experiment (50 confirmed cache misses)

Settings: unique questions + `force_miss=True` + `skip_cache_store=True`; `HW10_MOCK_LLM=1` for agent stages (same idea as HW8 timing runs). All 50 verified `cache_hit=false`.

| Stage | p50 (ms) | p95 (ms) | % of cache-miss end-to-end |
| --- | ---: | ---: | ---: |
| Cache lookup | 600.231 | 707.599 | 99.99 |
| Planner | 0.023 | 0.042 | 0.0 |
| Writer | 0.011 | 0.019 | 0.0 |
| Reviewer | 0.026 | 0.037 | 0.0 |
| Queue wait (total) | 0.0 | 0.0 | 0.0 |
| Evaluation | 0.021 | 0.033 | 0.0 |

Dominant in this mock-LLM run: **cache_lookup** (Redis + HF embed). Optimize embedding / Redis path first here. In-process path ⇒ queue wait = 0.

Live-Ollama sample (avg % of e2e from `miss-246adb0763` + `part2-d75168393967`): eval ~35%, cache_lookup ~25%, reviewer ~16%, writer ~13%, planner ~10%. With a real judge+LLM, **optimize Evaluation / Reviewer first**.

Cache-hit latency stays separate (Summary e2e + Trace lookup hit path; sample hit lookup ~1114 ms).
