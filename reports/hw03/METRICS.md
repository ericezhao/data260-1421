# Retrieval comparison

k = 5. Cosine and recall are means over the five questions. Recomputed from raw/summary.csv.

| Technique | Chunks | Avg chunk length | Top-1 cosine | Mean cosine @ k | Recall@k | Mean retrieval latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| token-based chunking | 1168 | 2006.1 | 0.574 | 0.542 | 0.8 | 6.8 |
| semantic chunking | 765 | 2758.7 | 0.582 | 0.537 | 1.0 | 6.8 |
| sentence-window chunking | 15204 | 977.2 | 0.588 | 0.556 | 0.8 | 10.0 |
