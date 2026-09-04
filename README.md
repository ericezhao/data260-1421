# Personal Configuration

- Name: Eric Zhao
- SID4: 1421
- PORT_BASE: 8521
- PREFIX: s1421
- SEED: 1421
- VERIFY_SEED: 261421
- DOMAIN_ID: 5
- Assigned domain: Local restaurant inspections

## Homework 1
## Part 1: Web Form and Docker

From the repository root:

```bash
cd code
docker build -t s1421-inspections .
docker run --rm -p 8521:8521 s1421-inspections
```

Open [http://localhost:8521](http://localhost:8521). The form is also available as `code/web_application/web_app.html`.

## Part 2: Agentic AI

```bash
conda activate data260-hw1
ollama list

python code/agents_demo.py \
  --title "Yakitori Restaurant Inspections" \
  --content "Observed multiple live flies landing on clean food-contact storage racks and food prep counters; small rodent droppings noted near the dry storage shelving baseboards."
```

## Part 3: Non-Determinism Experiment

```bash
python code/run_nondeterminism.py
```

## Part 4: Model Client and Token Accounting

Activate the required Python environment and confirm that Ollama is running:

```bash
conda activate data260-hw1
ollama list
```

Run the reproducible five-turn conversation and show `/stats` after turns 3 and 5:

```bash
python code/hw1_client.py \
  --script reports/hw01/cases/five_turn_conversation.json \
  --stats-after 3 5 \
  --json-output reports/hw01/raw/token_turns.json
```

Run the client interactively:

```bash
python code/hw1_client.py
```

Interactive commands:

- `/stats` prints turn count, cumulative token counts, serialized conversation-history length, and message count. It does not add a message to the conversation.
- `/exit` exits and prints cumulative input tokens, output tokens, and turn count.

## Token and Conversation Questions

### Why is prior conversation context resent with every turn?

Each model request is stateless. To let the model respond as part of an ongoing conversation, the client sends the system prompt and earlier user/assistant messages again with the new user message.

### How is a system prompt different from a user message?

A system prompt sets the model's overall role and behavior, such as the bullet-only code-review format. A user message supplies the current request. The system instruction has higher priority and applies across the conversation.

### Why do input tokens grow over a conversation?

Every new request includes the prior conversation, so the input contains more text after each turn. Earlier messages may be counted repeatedly because they are sent again as context.

### What eventually limits that growth?

The model has a finite context window. Once the system prompt, history, and new request approach that limit, the client must remove, summarize, or truncate older context. Increasing input size also increases latency and resource use before the hard limit is reached.

## Homework 2

