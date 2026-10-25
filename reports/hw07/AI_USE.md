# HW7 AI use

**1. What I used an AI assistant for, and what I did myself**

I used Cursor for most of the HW7 implementation, starting from the assignment and the DATA236 Demo 7 JWT sample: JWT login and roles on my inspection routes, the repaired agent loop, Reflexion, Bay Wheels tools and UI, injection fixtures, and the file-tool safety gate. I kept the demo's `security.py` / `dependencies.py` / OAuth2 form login shape and mapped roles onto `/api/inspections` instead of adding a second generic API.

I ran the Part 2 and Part 3 Ollama sweeps myself, checked the numbers in `METRICS.md` against the raw files, and I will take the screenshots and put together `Zhao_HW7.pdf`.

**2. One AI output that was wrong or unsuitable**

An early `/auth/login` handler lost its `@app.post` decorator during an edit. TestClient then returned 405, and `/auth/login` was missing from the route table even though `/auth/me` still worked.

**3. How I detected the problem**

Listing FastAPI routes showed only `GET /auth/me` under `/auth`, and a form login POST returned 405. That is a missing route registration, not a bad password.

**4. What I changed and why it works now**

I put `@app.post("/auth/login", response_model=schema.Token)` back on the login function. Login again returns a bearer token for `reader` / `writer` / `moderator`, and the role checks return 403 / 201 / 204 as required.
