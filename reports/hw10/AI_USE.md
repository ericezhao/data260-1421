# AI_USE - HW10

SID4 1421.

1. What AI helped with / what I did  
   Used AI to help scaffold Streamlit pages, span helpers, and GEval-style judge wiring. I wrote the 20 `eval_cases.json` drafts in the inspection domain and assigned `human_labels.csv` myself **before** any judge scores (freeze commit `75f93af`). I ran Redis Stack, Kafka, Ollama, and the Part2/3/4 scripts locally.

2. One wrong or independently verified item  
   The first Final-vs-Draft judge call scored **5** even though `draft == final` on `part2-d75168393967`. That would have forced a fake “improvement” story.

3. How I detected / verified it  
   Diffed `raw/messages/part2-d75168393967.json` plan/draft/final; lengths matched and strings were identical. Re-read the HW PDF line: if final did not improve, report that and do not force a positive conclusion.

4. What I changed  
   Added an identical-text rule (score 3, diff 0) for Final-vs-Draft, updated `part2_eval.json`, and documented Reviewer rubber-stamp behavior in METRICS. Kept human labels unchanged after seeing judge scores.
