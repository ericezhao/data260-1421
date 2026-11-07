# Part 2/3 semantic cache — same pattern as lecture slide (redisvl.SemanticCache).
# HW similarity threshold (e.g. 0.85) maps to redisvl distance ≈ 1 - similarity.
# Extra vs slide: filterable data_version so Part 3.5 can invalidate stale answers.
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw09.config import DEFAULT_THRESHOLD, EMBED_MODEL, PREFIX
from hw09.redis_client import get_redis

# slide uses ttl=3600; HW also needs data-version invalidation
DEFAULT_TTL = int(os.getenv("HW9_CACHE_TTL", "3600"))


def _sim_to_distance(similarity):
    return max(0.0, 1.0 - float(similarity))


def _distance_to_sim(distance):
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))


class SemanticResponseCache:
    def __init__(self, threshold=DEFAULT_THRESHOLD, redis_client=None, ttl=DEFAULT_TTL):
        self.threshold = float(threshold)
        self.ttl = None if ttl is None else int(ttl)
        self.redis = redis_client or get_redis(decode_responses=True)
        self.version_key = f"{PREFIX}:data_version"
        self._cache_name = f"{PREFIX}_llmcache"
        self._sc = self._make_semantic_cache()

    def _make_semantic_cache(self):
        # require Redis Stack / Redis 8 query engine (vector index)
        try:
            self.redis.execute_command("FT._LIST")
        except Exception as e:
            raise RuntimeError(
                "HW9 semantic cache needs Redis Stack (RediSearch). "
                "Start: docker compose -f code/hw09/docker-compose.yml up -d"
            ) from e

        from redisvl.extensions.cache.llm import SemanticCache
        from redisvl.utils.vectorize import HFTextVectorizer

        cache = SemanticCache(
            name=self._cache_name,
            redis_client=self.redis,
            distance_threshold=_sim_to_distance(self.threshold),
            ttl=self.ttl,
            vectorizer=HFTextVectorizer(model=EMBED_MODEL),
            filterable_fields=[{"name": "data_version", "type": "numeric"}],
            overwrite=True,
        )
        print(
            f"[semcache] redisvl name={self._cache_name} "
            f"sim>={self.threshold} dist<={_sim_to_distance(self.threshold):.3f} "
            f"ttl={self.ttl} model={EMBED_MODEL}"
        )
        return cache

    def get_data_version(self):
        v = self.redis.get(self.version_key)
        return int(v) if v is not None else 1

    def set_data_version(self, value):
        self.redis.set(self.version_key, int(value))

    def clear(self):
        try:
            self._sc.clear()
        except Exception as e:
            print(f"[semcache] clear warn: {e}")

    def put(self, query, answer, data_version=None):
        version = self.get_data_version() if data_version is None else int(data_version)
        # slide: cache.store(prompt=..., response=...)
        return self._sc.store(
            prompt=query,
            response=answer,
            filters={"data_version": version},
            metadata={"ts": time.time()},
        )

    def search(self, query, threshold=None):
        """Hit if redisvl distance <= (1 - similarity_threshold) and data_version matches."""
        from redisvl.query.filter import Num

        thr = self.threshold if threshold is None else float(threshold)
        current_version = self.get_data_version()
        dist_thr = _sim_to_distance(thr)
        filt = Num("data_version") == current_version

        # slide: hits = cache.check(prompt=query, num_results=1)
        hits = self._sc.check(
            prompt=query,
            num_results=1,
            filter_expression=filt,
            distance_threshold=dist_thr,
        )
        if hits:
            best = hits[0]
            dist = best.get("vector_distance", best.get("distance"))
            return {
                "hit": True,
                "similarity": _distance_to_sim(dist),
                "answer": best.get("response"),
                "cached_query": best.get("prompt"),
                "entry_id": best.get("entry_id") or best.get("id"),
                "data_version": current_version,
            }

        # miss: still report nearest neighbor similarity (for logs / Part2)
        loose = self._sc.check(
            prompt=query,
            num_results=1,
            filter_expression=filt,
            distance_threshold=2.0,
        )
        best_sim = 0.0
        cached_q = None
        entry_id = None
        if loose:
            dist = loose[0].get("vector_distance", loose[0].get("distance"))
            best_sim = _distance_to_sim(dist)
            cached_q = loose[0].get("prompt")
            entry_id = loose[0].get("entry_id") or loose[0].get("id")
        return {
            "hit": False,
            "similarity": best_sim,
            "answer": None,
            "cached_query": cached_q,
            "entry_id": entry_id,
            "data_version": current_version,
        }
