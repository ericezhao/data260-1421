# Reproducible Run Instructions — DATA-260 Homework 1

These instructions reproduce the Homework 1 model-client run and its machine-readable token-accounting output from the repository root.

## Personal Configuration

- SID4: 1421
- PORT_BASE: 8521
- PREFIX: `s1421`
- SEED: 1421
- VERIFY_SEED: 261421
- DOMAIN_ID: 5
- Assigned domain: Local restaurant inspections

## 1. Start from the repository root

Run all commands below from the root of the Homework 1 repository.

## 2. Activate the Python environment

```bash
conda activate data260-hw1
```

## 3. Confirm the local Ollama model service is available

```bash
ollama list
```

Confirm that the local model used for the homework is available before continuing.

## 4. Run the reproducible five-turn conversation

The frozen conversation input is stored at:

```text
reports/hw01/cases/five_turn_conversation.json
```

Run:

```bash
python code/hw1_client.py \
  --script reports/hw01/cases/five_turn_conversation.json \
  --stats-after 3 5 \
  --json-output reports/hw01/raw/token_turns.json
```

This command runs the same five-turn scripted conversation, prints `/stats` after turns 3 and 5, and writes the machine-readable results to:

```text
reports/hw01/raw/token_turns.json
```

## 5. Optional interactive run

To run the same client interactively:

```bash
python code/hw1_client.py
```

Available interactive commands:

- `/stats` — prints turn count, cumulative token counts, serialized conversation-history length, and message count without adding a new conversation message.
- `/exit` — exits the client and prints cumulative input tokens, output tokens, and turn count.

## 6. Reproducibility artifacts

The repository contains the following supporting artifacts under `reports/hw01/`:

- `RUN_LOG.txt` — recorded console output from the Part 3 experiment and the Part 4 five-turn conversation.
- `AI_USE.md` — answers to the four AI-use questions.
- `cases/five_turn_conversation.json` — frozen scripted conversation used by the command above.
- `raw/token_turns.json` — machine-readable token-accounting output.
- `METRICS.md` — reported experiment metrics.
- `verification.json` — Homework 1 verification results.

For reproducibility, keep the same repository version, local model/configuration, input case, and command-line arguments when comparing results.
