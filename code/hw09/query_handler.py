# Part 2 ingress: semantic cache in front of the agent path
import time

from hw09.agent_path import run_agent_pipeline
from hw09.config import DEFAULT_THRESHOLD
from hw09.semantic_cache import SemanticResponseCache


class CachedQA:
    def __init__(self, threshold=DEFAULT_THRESHOLD, cache=None):
        self.cache = cache or SemanticResponseCache(threshold=threshold)
        self.threshold = float(threshold)

    def ask(self, question, threshold=None):
        thr = self.threshold if threshold is None else float(threshold)
        t0 = time.perf_counter()
        lookup = self.cache.search(question, threshold=thr)
        if lookup["hit"]:
            latency_ms = (time.perf_counter() - t0) * 1000
            print(
                f"[cache HIT] sim={lookup['similarity']:.3f} "
                f"latency_ms={latency_ms:.1f} q={question!r}"
            )
            return {
                "question": question,
                "answer": lookup["answer"],
                "is_cached": True,
                "similarity": lookup["similarity"],
                "latency_ms": latency_ms,
                "cached_query": lookup["cached_query"],
                "data_version": lookup["data_version"],
            }

        print(f"[cache MISS] best_sim={lookup['similarity']:.3f} q={question!r}")
        t1 = time.perf_counter()
        result = run_agent_pipeline(question)
        answer = result["answer"]
        self.cache.put(question, answer)
        latency_ms = (time.perf_counter() - t0) * 1000
        agent_ms = (time.perf_counter() - t1) * 1000
        print(f"[cache STORE] agent_ms={agent_ms:.1f} total_ms={latency_ms:.1f}")
        return {
            "question": question,
            "answer": answer,
            "is_cached": False,
            "similarity": lookup["similarity"],
            "latency_ms": latency_ms,
            "cached_query": None,
            "data_version": self.cache.get_data_version(),
        }
