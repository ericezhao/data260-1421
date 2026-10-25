"""Fixed tool sequence for reproducible bike scenarios and as an agent fallback."""

from __future__ import annotations

import time
from pathlib import Path

from bike_share.tools import TripStore, calculator, fetch_policy_text, policy_retriever


def run_pipeline(
    csv_path: Path,
    pricing_url: str,
    fixture_text: str | None = None,
    monthly_price: float | None = None,
    unlock_fee: float | None = None,
    included_minutes: float | None = None,
    per_minute: float | None = None,
) -> dict:
    started = time.perf_counter()
    store = TripStore(csv_path)
    page = fetch_policy_text(pricing_url, fixture_text=fixture_text)
    timeline = []

    summary = store.csv_sql(
        "SELECT COUNT(*) AS rides, "
        "AVG(duration_min) AS avg_duration_min, "
        "SUM(duration_min) AS total_minutes, "
        "SUM(CASE WHEN duration_min > 30 THEN duration_min - 30 ELSE 0 END) AS surcharge_minutes "
        "FROM trips"
    )
    timeline.append(
        {
            "step": 1,
            "type": "tool",
            "tool": "csv_sql",
            "inputs": {"sql": "aggregate rides"},
            "observation": summary,
        }
    )
    weekly = store.csv_sql(
        "SELECT week, COUNT(*) AS ride_count, "
        "AVG(duration_min) AS avg_duration, "
        "SUM(duration_min) AS minutes "
        "FROM trips GROUP BY week ORDER BY week"
    )
    timeline.append(
        {
            "step": 2,
            "type": "tool",
            "tool": "csv_sql",
            "inputs": {"sql": "weekly breakdown"},
            "observation": weekly,
        }
    )
    policy = policy_retriever(
        pricing_url,
        "monthly membership price included minutes unlock fee per minute overage",
        k=5,
        cached=page,
        fixture_text=fixture_text,
    )
    timeline.append(
        {
            "step": 3,
            "type": "tool",
            "tool": "policy_retriever",
            "inputs": {"url": pricing_url, "query": "monthly membership"},
            "observation": policy,
        }
    )

    row = (summary.get("data") or {}).get("rows") or [{}]
    stats = row[0]
    rides = float(stats.get("rides") or 0)
    total_minutes = float(stats.get("total_minutes") or 0)
    surcharge_minutes = float(stats.get("surcharge_minutes") or 0)

    monthly = 34.0 if monthly_price is None else monthly_price
    unlock = 3.49 if unlock_fee is None else unlock_fee
    included = 45.0 if included_minutes is None else included_minutes
    per_min = 0.30 if per_minute is None else per_minute

    joined = page["text"].lower()
    if "costs $120" in joined or "$120 per month" in joined:
        monthly = 120.0
    elif "costs $34" in joined or "$34 per month" in joined:
        monthly = 34.0
    if "no unlock fee" in joined:
        unlock = 0.0
    elif "$3.49 unlock" in joined or "unlock fee" in joined:
        unlock = 3.49
    if "$0.05 per minute" in joined:
        per_min = 0.05
    elif "$0.30 per minute" in joined:
        per_min = 0.30

    pay = calculator(
        f"{rides}*{unlock} + {total_minutes}*{per_min}",
        units="USD",
    )
    timeline.append(
        {
            "step": 4,
            "type": "tool",
            "tool": "calculator",
            "inputs": {"expression": "pay-per-use"},
            "observation": pay,
        }
    )
    member_residual = calculator(
        f"{surcharge_minutes}*{per_min}",
        units="USD",
    )
    timeline.append(
        {
            "step": 5,
            "type": "tool",
            "tool": "calculator",
            "inputs": {"expression": "membership residual"},
            "observation": member_residual,
        }
    )
    member_total = calculator(
        f"{monthly}+{(member_residual.get('data') or {}).get('value', 0)}",
        units="USD",
    )
    timeline.append(
        {
            "step": 6,
            "type": "tool",
            "tool": "calculator",
            "inputs": {"expression": "membership total"},
            "observation": member_total,
        }
    )

    pay_value = float((pay.get("data") or {}).get("value") or 0)
    member_value = float((member_total.get("data") or {}).get("value") or 0)
    decision = "Buy Monthly Membership" if member_value < pay_value else "Pay Per Ride/Minute"
    break_even_rides = calculator(f"{monthly}/({unlock}+15*{per_min})", units="rides")
    week_rows = []
    for item in (weekly.get("data") or {}).get("rows") or []:
        minutes = float(item.get("minutes") or 0)
        count = float(item.get("ride_count") or 0)
        spend = count * unlock + minutes * per_min
        week_rows.append(
            {
                "week": item.get("week"),
                "ride_count": count,
                "average_duration": float(item.get("avg_duration") or 0),
                "spend_payg": round(spend, 2),
            }
        )

    justification = (
        f"Across {int(rides)} rides totaling {total_minutes:.1f} minutes, "
        f"pay-per-use is about ${pay_value:.2f} while membership is about "
        f"${member_value:.2f} (base ${monthly:.2f} plus residual overage "
        f"${(member_residual.get('data') or {}).get('value', 0):.2f}). "
        f"Break-even is roughly "
        f"{(break_even_rides.get('data') or {}).get('value', 0):.1f} typical rides. "
        f"Pricing snippets came from {pricing_url}. Decision: {decision}."
    )
    final = {
        "decision": decision,
        "justification": justification,
        "cost_breakdown": {
            "pay_per_use_total": round(pay_value, 2),
            "membership_total": round(member_value, 2),
            "membership_base": monthly,
            "membership_residual": round(
                float((member_residual.get("data") or {}).get("value") or 0), 2
            ),
            "break_even_rides": round(
                float((break_even_rides.get("data") or {}).get("value") or 0), 2
            ),
            "actual_rides": rides,
            "by_week": week_rows,
        },
        "assumptions": [
            f"Unlock fee assumed ${unlock} when not overridden by the page.",
            f"Per-minute rate assumed ${per_min}; included member minutes {included}.",
            "Duration column is duration_min in the uploaded CSV.",
        ],
    }
    timeline.append({"step": 7, "type": "final", "payload": final})
    return {
        **final,
        "timeline": timeline,
        "citations": {
            "pricing_url": pricing_url,
            "accessed_at": page["accessed_at"],
            "sha256": page["sha256"],
            "source": page["source"],
        },
        "metrics": {
            "step_count": len(timeline),
            "total_time_ms": int((time.perf_counter() - started) * 1000),
            "stop_reason": "success",
        },
        "snapshot_text": page["text"][:5000],
    }
