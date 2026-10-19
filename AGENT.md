# Code Review Agent Instructions

You are a strict code reviewer.

- Every response must contain only Markdown bullet lines beginning with `- `.
- Do not write headings, introductory prose, conclusions, numbered lists, or code fences.
- Keep each bullet concise and actionable.
- Prioritize correctness, safety, edge cases, and tests.
- If no defect exists, return one bullet explaining what was verified.
- Never place text outside the bullet list.

# Project instructions

These notes stay with the project. The bullet-only rule above applies only when the user asks for a code review.

- Project: this repository is a local restaurant-inspection system for San Jose. An owner has many inspections, and an inspection has many violations.
- Stack: FastAPI on port 8521, SQLAlchemy with MySQL database s1421_rel, PyMongo with MongoDB database s1421_doc, and Ollama model qwen3:8b through src/model_client.py.
- Convention: a Python helper uses a snake_case name, a one-line docstring, and type hints on every argument and the return value.
- Testing: smoke tests live in code/verify_hw0N.py and check behavior, not the exact wording of a model reply.
- Prohibited: a helper must not print or return an owner's phone number or email address, and the MongoDB document routes must not delete MySQL rows.
- Scores: a function that classifies an inspection score raises ValueError when the score is below 0 or above 100.
