# AI Use — Homework 3

## 1. What I used an AI assistant for, and what I did myself

I used an AI assistant to learn Bootstrap (layout, Navbar/Card/Button/Alert, and why the CDN classes work in the templates) and the idea of retrieval-only RAG, then to sketch how the homework maps onto chunking → in-memory FAISS index → top-k retrieve → cosine / latency etc. It also helped locate public domain PDFs for the restaurant-inspection corpus (FDA Food Code, California Retail Food Code, Santa Clara County DEH placarding handout).

I wrote most of `code/auth.py`, the templates, and `code/hw03_retrieve.py` myself. The assistant mainly corrected small details after I ran the code.

## 2. One AI-produced output that was wrong or unsuitable, or one thing I independently verified

`TemplateResponse` calls followed an older Starlette pattern and put the context dict first. On FastAPI 0.141 / Starlette 1.6 that raises `TypeError` because `request` must be the first argument: `TemplateResponse(request, name, context)`.

## 3. How I detected the problem or verified the result

`GET /login` returned 500. The traceback pointed at `TemplateResponse`. I compared the installed Starlette version with the sample call order and the current FastAPI docs.

## 4. What I changed and why it works now

I changed every `TemplateResponse` in `auth.py` to pass `request` first. Login, home, and dashboard then rendered instead of crashing.
