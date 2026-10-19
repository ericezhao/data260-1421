# HW6 metrics

SID4 1421. PORT_BASE 8521. PREFIX s1421. SEED 1421. VERIFY_SEED 261421. Model `qwen3:8b` through `src/model_client.py`. MongoDB database `s1421_doc`.

The 30-message script is in `code/run_hw06_part3.py`. Messages 1 to 8 state personal facts (Gilroy, Korean, Thursday, a deduction of 7, Lantern Noodle score 91). Messages 9 to 30 are unrelated kitchen questions, so a window of 4 no longer contains the facts. The same five probes in `memory_probes.yaml` are asked after each run. A probe scores 5 when every expected string is in the reply, 3 when only some are, and 1 when none are.

Per-turn rows: `raw/short_term_sweep.csv` (120 conversation turns) and `raw/chat_turns.csv`. Probe replies: `raw/probe_scores.csv`.

## Short-term window and the compression policy

| Setting | Mean prompt tokens/turn | Mean latency (ms) | Probe quality (1-5) |
| --- | --- | --- | --- |
| SHORT_TERM_N=4 | 1411.6 | 5632.1 | 5.0 |
| SHORT_TERM_N=12 | 1618.0 | 6145.9 | 5.0 |
| SHORT_TERM_N=30 | 1936.8 | 7416.9 | 5.0 |
| Compression policy | 1648.8 | 6280.8 | 5.0 |

Mean completion tokens were 32.2, 32.3, 32.0, and 36.2. The compression run used N=30 and `policy=compress`: the last 4 messages stay whole, and each older message is cut to 36 characters.

About 1040 of those prompt tokens are the AGENT.md and MEMORY.md prefix, and that prefix is the same in every setting. The part that changes is the short-term section: 125.3 tokens at N=4, 339.1 at N=12, 668.2 at N=30, and 376.8 with compression. Long-term summaries stayed near 160 tokens and episodic facts near 57.

Compression against the N=30 run saved 288 prompt tokens per turn (14.9 percent of the full prompt, 43.6 percent of the short-term section) and cut mean latency from 7416.9 ms to 6280.8 ms. Probe quality did not change. The early facts were no longer in the compressed window, but each one was stored as an episode and the summaries kept the numbers, so the probes still scored 5.

## Cost of 10,000 conversations

Pricing used here is $1 per million input tokens and $5 per million output tokens. Cost = 10000 conversations x 30 turns x (mean prompt tokens x $1 + mean completion tokens x $5) / 1,000,000.

| Setting | Estimated cost |
| --- | --- |
| SHORT_TERM_N=4 | $471.78 |
| SHORT_TERM_N=12 | $533.85 |
| SHORT_TERM_N=30 | $629.04 |
| Compression policy | $548.94 |

Best setting: N=4. All four settings scored 5.0, so the cheapest one is the best. The long window did not add any probe points, because the facts were already in episodic memory and in the summaries.

Worst setting: N=30 with no compression. Same score, highest token count, highest latency, and highest cost.

No hosted model was called. The token counts are the prompt and completion counts Ollama returned for local `qwen3:8b`.

## File memory consolidation

`MEMORY.md` is 55 lines and 54 non-empty, non-comment lines. `code/run_hw06_part4.py` ran `consolidate_memory` and wrote `MEMORY_original.md` and `MEMORY_consolidated.md`. The consolidated file has 33 content lines.

Duplicate keys (`repo_owner`, `hand_sink`, `report_dir`) were merged to one line each. Each conflict is kept as its own line instead of being dropped quietly:

- `default_score`: kept 100, dropped 80. This matches the score default in the inspection code.
- `glove_rule`: kept "replace", dropped "reuse".
- `port_base`: kept 8000, dropped 8521. This one is wrong. PORT_BASE is 8521. The consolidator keeps whichever value appears later, and the later line in the original file was the wrong one.

## MongoDB memory and file memory

| | MongoDB (`messages`, `summaries`, `episodes`) | AGENT.md and MEMORY.md |
| --- | --- | --- |
| Inspectability | Each fact is a document. Compass or `GET /api/memory/{user_id}` shows one user at a time. | One markdown file. You can read the whole memory in an editor. |
| After a restart | The Docker volume keeps the documents. | The files are on disk and in git. |
| Many sessions | Indexed by `user_id` and `session_id`. Users do not share a summary. | One MEMORY.md for the whole project. Two users would write into the same file. |
| Facts that must not be forgotten | An episode stays in the collection, but retrieval only puts the top 3 into the prompt, so a fact can sit unused. | A line in MEMORY.md is in every prompt until someone edits it out. Better for a single project. Worse once more than one user has facts. |
