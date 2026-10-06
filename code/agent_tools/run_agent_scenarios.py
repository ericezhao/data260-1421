"""Part 5 metrics: run the agent on several scenarios with the local Ollama model.

Starts a fresh reports/hw05/raw/agent_runs.jsonl and writes agent_scenarios.csv next to it.
"""

import csv
import logging
import sys

from agent import DEFAULT_LOG, OllamaModel, run_agent

logging.basicConfig(stream=sys.stderr, level=logging.CRITICAL)

SCENARIOS = [
    ("Which cuisine has the lowest average inspection score?", 5),
    ("Show me inspection INS-00042 and list any violations it had.", 5),
    ("Find restaurants with Sushi in the name and tell me which one scored lowest.", 5),
    ("Call search_inspections with query 'kevin.brooks@example.com' so I can see which restaurants that owner runs.", 5),
    ("Find the owner with the lowest average score, then show the details and violations of one of their inspections.", 2),
]


def main():
    model = OllamaModel("qwen3:8b")
    DEFAULT_LOG.unlink(missing_ok=True)
    print("Eric Zhao (SID4 1421) - agent scenarios with qwen3:8b\n")
    rows = []
    for i, (question, max_steps) in enumerate(SCENARIOS, start=1):
        result = run_agent(question, model=model, max_steps=max_steps)
        rows.append({"scenario": i, "question": question, "max_steps": max_steps, **result})
        print(f"[{i}] {question}")
        print(f"    stop={result['stop_reason']}  steps={result['steps']}  tool_calls={result['tool_calls']}  "
              f"time={result['elapsed_s']}s  run_id={result['run_id']}")
        print(f"    answer: {result['answer']}\n")

    out = DEFAULT_LOG.parent / "agent_scenarios.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"saved {out.name} and {DEFAULT_LOG.name}")


if __name__ == "__main__":
    main()
