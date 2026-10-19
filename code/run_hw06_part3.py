"""Replay one 30-message conversation under four memory settings and score five probes."""

import csv
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
import yaml

BASE = "http://127.0.0.1:8521"
ROOT = Path(__file__).resolve().parents[1]
HW06 = ROOT / "reports" / "hw06"
RAW = HW06 / "raw"
LOG = HW06 / "RUN_LOG.txt"
PROBES = HW06 / "memory_probes.yaml"

PLANTED = [
    "My inspection city is Gilroy.",
    "My favorite inspection cuisine is Korean.",
    "My inspection weekday is Thursday.",
    "My critical deduction is 7 points.",
    "My Lantern Noodle 150 score is 91 and the next step is a return visit.",
    "My personal cap is 93 whenever a violation is on the report.",
    "My badge number is 1421.",
    "My first sample counter serves skewers.",
]

FILLERS = [
    "How should a cook dry their hands after washing them at the hand sink? Please answer in two sentences and mention a clean towel or a dryer.",
    "What belongs on the floor of a walk-in, and what should never be stored there overnight? Keep the answer to two sentences.",
    "Describe one reason a cutting board should be washed between raw chicken and salad greens. Two sentences is enough.",
    "When is a sanitizer bucket useful on a prep line, and how often should the water be changed? Answer in two sentences.",
    "What should a manager do if a thermometer reads a hot holding pan below the safe range? Two sentences.",
    "Why do pots need to be air dried instead of stacked while they are still wet? Answer in two sentences.",
    "Name one record a kitchen keeps about receiving a delivery of raw meat. Keep it to two sentences.",
    "What is a simple way to keep ready-to-eat food off the bottom shelf? Answer in two sentences.",
    "How should wiping cloths be stored between uses on a prep table? Two sentences.",
    "What should staff do with a cracked plastic container that still looks clean? Answer in two sentences.",
    "Why is it a problem to thaw frozen food on a counter for a whole afternoon? Two sentences.",
    "What goes into a note about a repaired refrigerator gasket? Keep the answer to two sentences.",
    "How can a dishwasher confirm that the final rinse is hot enough? Answer in two sentences.",
    "What should happen to a can that is dented along the top seam? Two sentences.",
    "Why should a mop dry hanging, rather than sitting in a bucket? Answer in two sentences.",
    "What is one sign that a grease trap needs service before the weekend rush? Two sentences.",
    "How should cooked rice be cooled faster than leaving the pot on the stove? Answer in two sentences.",
    "What belongs in a short note after a pest control visit? Keep it to two sentences.",
    "Why should personal drinks stay off the prep table? Answer in two sentences.",
    "What should a closer check on the back door before locking up? Two sentences.",
    "How do you describe a clean ice machine scoop in a daily log? Answer in two sentences.",
    "What is a plain way to remind a new hire to change gloves after taking out trash? Two sentences.",
]

SETTINGS = [
    ("n4", 4, "none"),
    ("n12", 12, "none"),
    ("n30", 30, "none"),
    ("compress", 30, "compress"),
]


def score_answer(answer: str, probe: dict) -> int:
    text = (answer or "").lower()
    hits = []
    for item in probe["expect"]:
        if probe.get("match") == "word":
            hits.append(re.search(rf"\b{re.escape(item.lower())}\b", text) is not None)
        else:
            hits.append(item.lower() in text)
    if all(hits):
        return 5
    if any(hits):
        return 3
    return 1


def reset_user(user_id: str) -> None:
    from pymongo import MongoClient

    db = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)["s1421_doc"]
    for name in ("messages", "summaries", "episodes"):
        db[name].delete_many({"user_id": user_id})


def post_chat(client: httpx.Client, payload: dict) -> dict:
    last = ""
    for attempt in range(1, 4):
        response = client.post("/api/chat", json=payload)
        if response.status_code == 200:
            return response.json()
        last = f"{response.status_code} {response.text[:300]}"
        print(f"  retry {attempt}: {last}", flush=True)
        time.sleep(2)
    raise RuntimeError(last)


def run_setting(client: httpx.Client, name: str, window: int, policy: str, probes: list[dict]):
    user_id = f"hw6-{name}"
    session_id = f"sess-{name}"
    reset_user(user_id)
    turns = []
    probe_rows = []
    for index, message in enumerate(PLANTED + FILLERS, start=1):
        data = post_chat(client, {
            "user_id": user_id,
            "session_id": session_id,
            "message": message,
            "short_term_n": window,
            "policy": policy,
            "run_label": name,
            "phase": "conversation",
        })
        usage = data["usage"]
        turns.append(usage)
        print(f"  turn {index:02d} prompt={usage['prompt_tokens']} latency_ms={usage['latency_ms']}", flush=True)
    scores = []
    for probe in probes:
        data = post_chat(client, {
            "user_id": user_id,
            "session_id": session_id,
            "message": probe["question"],
            "short_term_n": window,
            "policy": policy,
            "run_label": name,
            "phase": "probe",
        })
        points = score_answer(data["reply"], probe)
        scores.append(points)
        probe_rows.append({
            "setting": name,
            "probe_id": probe["id"],
            "score": points,
            "reply": data["reply"].replace("\n", " "),
        })
        print(f"  probe {probe['id']} score={points} reply={data['reply'][:120]!r}", flush=True)
    return turns, scores, probe_rows


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def main() -> None:
    probes = yaml.safe_load(PROBES.read_text(encoding="utf-8"))["probes"]
    RAW.mkdir(parents=True, exist_ok=True)
    print("Eric Zhao (SID4 1421)")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    summary_rows = []
    all_probes = []
    sweep_path = RAW / "short_term_sweep.csv"
    with httpx.Client(base_url=BASE, timeout=180) as client, sweep_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "setting", "phase", "turn", "prompt_tokens", "completion_tokens",
            "primer_tokens", "long_term_tokens", "short_term_tokens", "episodic_tokens", "latency_ms",
        ])
        writer.writeheader()
        for name, window, policy in SETTINGS:
            print(f"\n[{name}] short_term_n={window} policy={policy}", flush=True)
            turns, scores, probe_rows = run_setting(client, name, window, policy, probes)
            for index, usage in enumerate(turns, start=1):
                writer.writerow({
                    "setting": name,
                    "phase": "conversation",
                    "turn": index,
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "primer_tokens": usage["primer_tokens"],
                    "long_term_tokens": usage["long_term_tokens"],
                    "short_term_tokens": usage["short_term_tokens"],
                    "episodic_tokens": usage["episodic_tokens"],
                    "latency_ms": usage["latency_ms"],
                })
            all_probes.extend(probe_rows)
            prompt = mean([row["prompt_tokens"] for row in turns])
            completion = mean([row["completion_tokens"] for row in turns])
            latency = mean([row["latency_ms"] for row in turns])
            quality = mean(scores)
            cost = round(10000 * 30 * (prompt * 1.0 + completion * 5.0) / 1_000_000, 2)
            summary_rows.append({
                "setting": name,
                "short_term_n": window,
                "policy": policy,
                "mean_prompt_tokens": prompt,
                "mean_completion_tokens": completion,
                "mean_latency_ms": latency,
                "mean_probe_score": quality,
                "cost_10000_conversations_usd": cost,
            })
            print(f"  mean prompt={prompt} completion={completion} latency_ms={latency} probe={quality} cost=${cost}")
    with (RAW / "memory_cost_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    with (RAW / "probe_scores.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["setting", "probe_id", "score", "reply"])
        writer.writeheader()
        writer.writerows(all_probes)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{stamp}] part 3 short-term sweep\n")
        for row in summary_rows:
            handle.write(
                f"{row['setting']}: prompt={row['mean_prompt_tokens']} "
                f"completion={row['mean_completion_tokens']} latency_ms={row['mean_latency_ms']} "
                f"probe={row['mean_probe_score']} cost_usd={row['cost_10000_conversations_usd']}\n"
            )
    print("\nsaved short_term_sweep.csv, memory_cost_summary.csv, probe_scores.csv")


if __name__ == "__main__":
    main()
