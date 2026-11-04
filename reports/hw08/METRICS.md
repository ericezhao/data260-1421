# HW8 metrics

SID4 1421, PORT_BASE 8521, PREFIX s1421, SEED 1421, VERIFY_SEED 261421, DOMAIN_ID 5 (restaurant inspections).  
Agents: local `qwen3:8b` (HW1 Ollama client). Part2 journey + Part3 writers used `HW8_MOCK_LLM=1` so runs finish without waiting on Ollama; unset that env var for a live model run.  
Topics all use the `s1421_` prefix.

## Part 1 - Kafka request/response

| Item | Value |
| --- | --- |
| Request topic | `s1421_entity_requests` |
| Response topic | `s1421_entity_responses` |
| Operations | `CREATE_INSPECTION`, `GET_INSPECTION` |
| Store | in-memory dict in the worker |
| Demo | `python code/kafka_rpc/homework_demo.py` |
| Docker | `s1421-kafka`, `s1421-worker`, `s1421-api` on port 8521 |

Evidence: `RUN_LOG.txt` (CREATE then GET, same `correlation_id` echoed).

## Part 2 - Three-agent pipeline

| Stage | Reads | Writes |
| --- | --- | --- |
| Sender | - | `s1421_inbox` |
| Planner | `s1421_inbox` | `s1421_tasks` |
| Writer | `s1421_tasks` | `s1421_drafts` |
| Reviewer | `s1421_drafts` | `s1421_final` |

Final message has `correlation_id`, `status`, and `answer`.  
Example in RUN_LOG: `correlation_id=6e22e60c-...`, `status=approved`, score 8.

## Part 3 - Failure table

| Failure scenario | Before fix | After fix |
| --- | --- | --- |
| Duplicate delivery | Replaying CREATE with the same `correlation_id` would insert a second row | `PROCESSED` map returns the same `inspection_id` with `idempotent_replay` (`raw/duplicate_demo.json`, `raw/failure_results.json`) |
| Consumer killed mid-work | Auto-commit before finish can drop work | First consumer saw offset 55 and exited without commit; restart redelivered offset 55 then committed (`failure_results.json` -> `consumer_death`) |
| Poison message | Bad message can block the consumer loop | Retried twice (`_retries=2`), moved to `s1421_dead_letter` with `dead_letter_reason=poison message`; later messages still flow |
| Two partitions / two consumers | Related tasks can land on different partitions | Without key: 20 msgs used partitions `{0,1}`. With `entity_key`: all 20 stayed on partition `1` and finished in seq order 0..19 (`ordering_*.csv`) |

Raw files: `raw/failure_results.json`, `raw/ordering_without_key.csv`, `raw/ordering_with_key.csv`.

## HW2 vs Kafka (two benefits / two new responsibilities)

Benefits: (1) agents and the inspection worker can scale / restart on their own; (2) a Writer crash does not take down Planner or Reviewer.  
New responsibilities: (1) keep ordering with keys/partitions; (2) handle duplicates, commits, retries, and dead-letter messages yourself.

## Verify

`PYTHONPATH=code python code/verify_hw08.py` - local store checks, live Kafka CREATE/GET round-trip, and Part3 raw files present.
