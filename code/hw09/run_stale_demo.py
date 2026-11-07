# Part 3.5: stale answer + invalidation via data_version
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

from hw09.query_handler import CachedQA
from hw09.semantic_cache import SemanticResponseCache
from hw09.views_cache import InspectionDB

OUT = ROOT / "reports" / "hw09" / "raw" / "stale_invalidation.json"


def grade_answer(rel):
    return (
        f"Inspection {rel['inspection_id']} currently shows grade "
        f"{rel['grade_label']} (rel version {rel['version']})."
    )


def main():
    print("Eric Zhao SID4=1421 Part3.5 stale / invalidation")
    db = InspectionDB()

    # reset relation so the demo is readable: start at grade A / version 1
    db.conn.execute(
        "UPDATE s1421_rel SET grade_label = ?, version = ? WHERE inspection_id = ?",
        ("A", 1, "ins-001"),
    )
    db.conn.commit()
    rel = db.get_rel("ins-001")
    if not rel:
        raise SystemExit("missing s1421_rel for ins-001")

    cache = SemanticResponseCache(threshold=0.85)
    cache.clear()
    cache.set_data_version(rel["version"])
    qa = CachedQA(threshold=0.85, cache=cache)

    q = "What grade placard does inspection ins-001 currently show?"

    # 1) cache a version-dependent answer tied to s1421_rel
    ans1 = grade_answer(rel)
    cache.put(q, ans1, data_version=rel["version"])
    hit1 = qa.ask(q)
    print("first hit:", hit1["is_cached"], hit1["answer"])

    # 2) update the relation so the cached answer is stale (do NOT bump cache yet)
    rel2 = db.update_rel_grade("ins-001", "B")
    stale = qa.ask(q)
    print("stale hit:", stale["is_cached"], stale["answer"])

    # 3) invalidate by bumping the stored data-version marker
    cache.set_data_version(rel2["version"])
    lookup = cache.search(q)
    print("after bump search hit=", lookup["hit"], "sim=", round(lookup["similarity"], 3))
    fresh = grade_answer(rel2)
    cache.put(q, fresh, data_version=rel2["version"])
    after = qa.ask(q)

    payload = {
        "query": q,
        "before_update": {"rel": rel, "cached_answer": ans1, "hit": hit1},
        "after_update_before_invalidate": {
            "rel": rel2,
            "returned": stale,
            "stale": stale["answer"] == ans1 and rel2["grade_label"] != rel["grade_label"],
        },
        "after_invalidate": {
            "data_version": cache.get_data_version(),
            "lookup_after_bump": lookup,
            "returned": after,
            "fresh_answer": fresh,
        },
        "strategy": (
            "Each cache entry stores data_version. A global "
            f"{cache.version_key} marker is compared on lookup; "
            "bumping it after s1421_rel changes makes old entries ineligible."
        ),
        "tradeoff": (
            "Simple and safe for linked facts, but any bump can invalidate "
            "unrelated cached answers too (broader than key-level delete)."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2)[:1400])
    db.close()


if __name__ == "__main__":
    main()
