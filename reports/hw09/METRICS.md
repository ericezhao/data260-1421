# HW9 metrics

SID4 1421, PORT_BASE 8521, PREFIX s1421, SEED 1421, VERIFY_SEED 261421, DOMAIN_ID 5 (restaurant inspections).  
Model: `qwen3:8b` when live; demos here mostly used `HW9_MOCK_LLM=1` for agent answers. Embeddings: `sentence-transformers/all-MiniLM-L6-v2`.  
Redis: **Redis Stack** (`redis/redis-stack-server` via `code/hw09/docker-compose.yml`, container `s1421-redis`).  
Semantic cache: lecture-slide pattern **`redisvl.SemanticCache`** (`check` / `store`, `ttl=3600`, index `s1421_llmcache`). HW cosine threshold (e.g. 0.85) maps to `distance_threshold = 1 - similarity` (0.15). Entries also carry filterable `data_version` for Part 3.5 invalidation.  
Part1 view keys / version marker still start with `s1421:`. Part1 can use fakeredis if Stack is down; Part2/3 require Stack.

## Part 1 - view counter

Method: `InspectionDB.increment_inspection_views(inspection_id)`  
Redis key: `s1421:views:inspection:{id}` via `INCR`.  
Every 10 increments: UPDATE sqlite `view_count` + log `Synced views to database`.

Demo (25 accesses on `ins-001`): sync at 10 and 20; final redis total 25; sqlite `view_count=20`.

## Part 2 - semantic cache (threshold 0.85)

12 queries (exact / paraphrase / new). Results in `raw/part2_results.json` (redisvl + Stack):

| Metric | Value |
| --- | --- |
| Hit rate | 25.0% (3/12) |
| Avg latency cached | ~6.2 ms |
| Avg latency uncached | ~18 ms (mock LLM; first process also pays model load) |

## Part 3 - threshold sweep

Cases: `code/hw09/cache_cases.yaml` (40 labeled; not edited after sweep).  
Backend: redisvl vector index on Redis Stack.

| Threshold | Hit rate | False-hit rate | Mean latency (ms) | Total cost |
| --- | --- | --- | --- | --- |
| 0.75 | 0.525 | 0.15 | 12.44 | 3.38 |
| 0.80 | 0.525 | 0.15 | 11.58 | 3.38 |
| 0.85 | 0.475 | 0.125 | 12.47 | 2.92 |
| 0.90 | 0.375 | 0.05 | 13.93 | 1.50 |
| 0.95 | 0.275 | 0.025 | 15.22 | 1.08 |

Cost model: miss = $0.02 (extra agent path), false-hit = $0.50 (wrong answer / support).  
`total_cost = misses*0.02 + false_hits*0.50`.  
Ship threshold: **0.95** (lowest total cost; false-hit rate also lowest).

### One false hit (threshold 0.85, case F02)
- Cached query: `Is Japanese cuisine usually high risk for raw fish?`
- Incoming query: `Is Mexican cuisine usually high risk for raw fish?`
- Similarity: ~0.86
- Cached answer returned: the Japanese/raw-fish answer from cache
- Correct answer: should miss and answer about Mexican cuisine risk (not reuse Japanese)
- Why confused: shared template words ("cuisine", "high risk", "raw fish") pull embeddings together even though the cuisine slot changed.

Stale / invalidation: each redisvl entry stores filterable `data_version`; lookups filter `Num("data_version") == current` (`s1421:data_version`). Updating `s1421_rel` without bumping the marker can return a stale hit; bumping the marker drops old entries from search. Trade-off: simple but a global bump can invalidate unrelated answers too.

## Part 4 - four variants (test_data.json)

| Variant | Correct | Incorrect | Avg attempts | Avg latency (ms) |
| --- | --- | --- | --- | --- |
| Baseline | 5 | 1 | 1.0 | ~0.03 |
| Evaluator Repair | 6 | 0 | 1.167 | ~0.03 |
| Lesson Memory | 6 | 0 | 1.333 | ~0.03 |
| Validated Improvement | 6 | 0 | 1.333 | ~0.03 |

Lesson kept after validation (5/5 stayed 5/5).  
Revision demo: attempt1 REVISE -> attempt2 PASS.  
Lesson reuse demo: later score question loads `lesson_001` and passes on attempt 1.  
Details: `raw/part4_results.json`.

## Verify

`PYTHONPATH=code:.deps python code/verify_hw09.py` → 7/7 PASS (Part1 view check can use fakeredis; semantic import only).
