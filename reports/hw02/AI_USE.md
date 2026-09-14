# AI Use — Homework 2

## 1. What I used an AI assistant for, and what I did myself

I used Cursor to help split the LangGraph files (`state`, `nodes`, `router`, `schema`, `workflow`), write the Part 4 experiment runner, and auto-fill `METRICS.md` from the JSON results. I also used it to compare the repo against the Homework 2 PDF.

I set up the FastAPI records page on port 8521, chose restaurant name / cuisine as the primary and secondary fields, ran the schema / ceiling / adversarial experiments locally with `qwen3:8b`, and took the Terminal.app screenshots for the report.

## 2. One AI-produced output that was wrong or unsuitable

The first adversarial input was too easy. The model ignored the bad instructions and returned three legal tags on the first try (`valid_first_attempt`), so it did not show a schema failure or a retry.

## 3. How I detected the problem or verified the result

I ran that input through the graph and read the printed `outcome`. There was no `[Planner] schema error` and `planner_attempts` stayed at 1, which is the opposite of what Part 4 question 5 needs.

## 4. What I changed and why it works now

I rewrote `reports/hw02/cases/adversarial_input.json` so the model is told to emit one-letter tags `a,b,c` as a comma string and a 40-word summary. Pydantic then rejects `data.tags` (not a list of 3 tags each 3–30 characters). The five recorded runs all hit the ceiling.
