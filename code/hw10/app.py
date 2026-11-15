# Part 1 streamlit ops dashboard
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]

import pandas as pd
import streamlit as st

from hw10.config import (
    EVAL_RESULTS_DIR,
    JUDGE_METRICS_JSON,
    LATENCY_JSON,
    MESSAGES_DIR,
    REPORTS,
    SUMMARY_JSON,
    TRACE_INDEX_JSON,
)
from hw10.ops_summary import build_summary
from hw10.tracing import SpanStore


@st.cache_resource
def get_span_store():
    return SpanStore()


@st.cache_data(ttl=30)
def load_json(path_str):
    p = Path(path_str)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


@st.cache_data(ttl=30)
def load_eval_table():
    rows = []
    if not EVAL_RESULTS_DIR.exists():
        return pd.DataFrame()
    for p in sorted(EVAL_RESULTS_DIR.glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        metrics = rec.get("metrics") or {}
        row = {
            "correlation_id": rec.get("correlation_id"),
            "question": (rec.get("question") or "")[:80],
            "cache_hit": rec.get("cache_hit"),
        }
        for name, m in metrics.items():
            row[f"{name}_score"] = m.get("score")
        rows.append(row)
    return pd.DataFrame(rows)


st.set_page_config(page_title="HW10 s1421", layout="wide")
st.title("HW10 ops dashboard")
st.caption("s1421 restaurant inspections | correlation_id = trace_id")

page = st.sidebar.radio("Page", ["Summary", "Evaluation", "Trace lookup"])

if page == "Summary":
    st.header("1.1 Summary")
    if st.button("Refresh"):
        build_summary()
        st.cache_data.clear()
    summary = load_json(str(SUMMARY_JSON)) or build_summary()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("requests", summary.get("n_requests"))
    c2.metric("cache hit rate", f"{(summary.get('cache_hit_rate') or 0) * 100:.1f}%")
    c3.metric("error rate", f"{(summary.get('error_rate') or 0) * 100:.2f}%")
    e2e = summary.get("e2e_latency_ms") or {}
    c4.metric("e2e p50 ms", e2e.get("p50"))

    st.subheader("hits vs misses")
    st.write(
        {
            "hits": summary.get("cache_hits"),
            "misses": summary.get("cache_misses"),
            "hit_rate": summary.get("cache_hit_rate"),
        }
    )
    st.subheader("latency")
    st.json(e2e)

    lat = load_json(str(LATENCY_JSON))
    if lat:
        st.subheader("cache-miss stage latency (part 4.3)")
        st.dataframe(pd.DataFrame(lat.get("stages") or []), use_container_width=True)
        st.write(lat.get("optimize_first") or "")
        st.caption("cache-hit latency is separate (see Trace lookup hit path)")

    st.subheader("time window / sources")
    st.write(summary.get("time_window"))
    st.write(summary.get("data_sources"))

elif page == "Evaluation":
    st.header("1.2 Evaluation")
    st.subheader("Part 2 scores")
    df = load_eval_table()
    if df.empty:
        st.warning("no eval results — run python -m hw10.run_part2_eval")
    else:
        st.dataframe(df, use_container_width=True)

    part2 = load_json(str(REPORTS / "raw" / "part2_eval.json"))
    if part2 and part2.get("metrics"):
        st.subheader("latest Part 2")
        for name, m in part2["metrics"].items():
            st.write(f"{name}: {m.get('score')} ({m.get('engine')})")
            st.caption(m.get("reason") or "")
        fvd = part2["metrics"].get("final_vs_draft") or {}
        score = fvd.get("score") or 0
        if score >= 4:
            note = "Reviewer improved the draft."
        elif score == 3:
            note = "Final about the same as draft (no real improvement)."
        else:
            note = "Final looked worse; not forcing a positive story."
        st.write("Final-vs-Draft:", score, "-", note)

    st.subheader("Part 3 judge check")
    jm = load_json(str(JUDGE_METRICS_JSON))
    if not jm:
        st.warning("no judge_metrics.json — run python -m hw10.run_part3_judge")
    else:
        agr = jm.get("agreement_run1") or {}
        rep = jm.get("repeatability") or {}
        a, b, c = st.columns(3)
        a.metric("Spearman", round(agr.get("spearman_rho") or 0, 4))
        b.metric("MAE", round(agr.get("mae") or 0, 4))
        c.metric("changed in 3x", rep.get("cases_with_any_change"))
        st.write(
            {
                "mean_abs_change": rep.get("mean_abs_change"),
                "max_abs_change": rep.get("max_abs_change"),
                "trust": jm.get("trust_gate"),
            }
        )
        if agr.get("pairs"):
            st.dataframe(pd.DataFrame(agr["pairs"]), use_container_width=True)
        st.write(
            "Read: Planner/Writer/Final scores show coordination. "
            "Judge trust comes from Spearman/MAE vs the frozen human labels."
        )

else:
    st.header("1.3 Trace lookup")
    idx = load_json(str(TRACE_INDEX_JSON)) or {}
    named = idx.get("named") or {}
    if named:
        st.write(
            "named traces:",
            {k: v for k, v in named.items() if k.startswith("cache") or k == "failed"},
        )
    store = get_span_store()
    choices = store.list_trace_ids()
    default = named.get("cache_miss_success") or (choices[0] if choices else "")
    tid = st.text_input("trace_id (= correlation_id)", value=default or "")
    if tid:
        spans = store.load(tid)
        if not spans:
            st.error("no spans for that id")
        else:
            order = ["cache_lookup", "planner", "writer", "reviewer", "eval", "queue_wait"]
            spans = sorted(
                spans,
                key=lambda s: (
                    order.index(s["stage"]) if s.get("stage") in order else 99,
                    s.get("start") or "",
                ),
            )
            st.subheader("journey")
            rows = [
                {
                    "stage": s.get("stage"),
                    "start": s.get("start"),
                    "end": s.get("end"),
                    "duration_ms": s.get("duration_ms"),
                    "status": s.get("status"),
                    "error": s.get("error"),
                    "cache_hit": s.get("cache_hit"),
                    "path": s.get("path"),
                }
                for s in spans
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            cl = next((s for s in spans if s.get("stage") == "cache_lookup"), None)
            if cl:
                if cl.get("cache_hit"):
                    st.success("CACHE HIT")
                else:
                    st.info("CACHE MISS")
            msg_path = MESSAGES_DIR / f"{tid}.json"
            if msg_path.exists():
                st.subheader("plan / draft / final")
                st.json(json.loads(msg_path.read_text(encoding="utf-8")))
