# AI_USE - HW9

SID4 1421.

1. What AI helped with / what I did  
   I used AI to help with some coding, and wirte the 40 `cache_cases.yaml` labels myself before running the sweep. 

2. One wrong or independently verified item  
   An early paraphrase ("What numbers can an inspection score be between?") only scored ~0.81 vs the seed, so at threshold 0.85 it was a miss even though I labeled it as should-hit.

3. How I detected / verified it  
   Part2 logs printed `best_sim≈0.81` on that paraphrase. Live path confirmed with Redis Stack `FT._LIST` + `redisvl.SemanticCache.check/store`.

4. What I changed  
   Kept the original labels and used the sweep table to justify shipping 0.95 instead of 0.85. `docker-compose.yml` uses `redis/redis-stack-server`; `semantic_cache.py` follows the slide `check`/`store`/`ttl` pattern, plus a filterable `data_version` for Part 3.5.
