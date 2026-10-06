# Part 5 - Reflection

Run: `b307d148` in `raw/agent_runs.jsonl` (scenario 5, `qwen3:8b`, `max_steps = 2`).
Request: "Find the owner with the lowest average score, then show the details and violations of one of their inspections."

**Start.** The harness logged a `start` event and built two messages: a system prompt listing the three tools with their argument types and the JSON reply format, and the user request. The step counter began at 0.

**Step 1.** The model replied `{"action": "tool", "tool": "score_summary", "inputs": {"group_by": "owner", "top": 1}}`. The harness parsed the JSON and passed it to `execute_tool`. That call checked the tool name, ran the safety rule (no email or phone number, so allowed), validated the inputs against `SummaryInput`, and queried MySQL through the retry wrapper. The envelope came back `ok: true`: James Lopez, 98 inspections, average 99.59. The harness logged the `tool_call` with its input and result and appended the result to the conversation as `TOOL_RESULT`.

**Step 2.** The model asked for `get_inspection` with `INS-00042`. The call was valid and succeeded, but that inspection belongs to Daniel Lopez (owner 7), not James Lopez. No tool lists inspections by owner, and the summary returns names rather than owner IDs, so the model guessed a code instead of admitting it could not continue.

**Stop.** The counter now equalled `max_steps`, so the loop ended before a third model call. The harness logged `stop_reason: "max_steps"`, 2 steps, 2 tool calls, and `answer: null`. This was neither a normal completion nor a safety block. The ceiling did its job: it stopped a run that was going in the wrong direction after a fixed cost.

**Takeaway.** The failure came from the tool set, not the loop. Returning `ownerId` from `score_summary` and adding an inspections-by-owner query would let the model finish this task in three steps.