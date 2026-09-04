import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_ROOT = PROJECT_ROOT / "reports" / "hw01"
RAW_ROOT = REPORT_ROOT / "raw"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def input_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_publish_package(stdout: str) -> dict[str, Any]:
    marker_position = stdout.rfind("Publish Package")
    if marker_position < 0:
        raise ValueError("Publish Package marker was not found in agents_demo.py output")

    json_start = stdout.find("{", marker_position)
    if json_start < 0:
        raise ValueError("Publish Package JSON object was not found")

    package, _ = json.JSONDecoder().raw_decode(stdout[json_start:])
    if not isinstance(package, dict):
        raise ValueError("Publish Package must be a JSON object")
    return package


def save_raw_results(
    results: list[dict[str, Any]],
    json_path: Path,
    csv_path: Path,
    model: str,
    case_path: Path,
    case_hash: str,
) -> None:
    payload = {
        "model": model,
        "input_file": str(case_path.relative_to(PROJECT_ROOT)),
        "input_sha256": case_hash,
        "result_count": len(results),
        "results": results,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "temperature",
                "run",
                "timestamp_utc",
                "latency_ms",
                "tags_json",
                "summary",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "temperature": result["temperature"],
                    "run": result["run"],
                    "timestamp_utc": result["timestamp_utc"],
                    "latency_ms": result["latency_ms"],
                    "tags_json": json.dumps(result["tags"]),
                    "summary": result["summary"],
                }
            )


def percentile(values: list[int], proportion: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot calculate a percentile for an empty list")
    if len(ordered) == 1:
        return float(ordered[0])

    position = (len(ordered) - 1) * proportion
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def metrics_for(results: list[dict[str, Any]]) -> dict[str, Any]:
    tag_sets = [
        {str(tag).strip().lower() for tag in result["tags"]}
        for result in results
    ]
    canonical_sets = {tuple(sorted(tag_set)) for tag_set in tag_sets}
    common_tags = set.intersection(*tag_sets) if tag_sets else set()
    tag_run_counts = Counter(tag for tag_set in tag_sets for tag in tag_set)
    singleton_tags = {tag for tag, count in tag_run_counts.items() if count == 1}
    latencies = [int(result["latency_ms"]) for result in results]

    return {
        "run_count": len(results),
        "distinct_tag_sets": len(canonical_sets),
        "tags_in_all_runs": sorted(common_tags),
        "tags_in_exactly_one_run": sorted(singleton_tags),
        "latency_p50_ms": percentile(latencies, 0.50),
        "latency_p95_ms": percentile(latencies, 0.95),
        "latency_p99_ms": percentile(latencies, 0.99),
    }


def display_tags(tags: list[str]) -> str:
    return ", ".join(f"`{tag}`" for tag in tags) if tags else "None"


def write_metrics(
    results: list[dict[str, Any]],
    temperatures: list[float],
    metrics_path: Path,
    case_path: Path,
    case_hash: str,
    model: str,
) -> None:
    grouped = {
        temperature: [
            result for result in results
            if float(result["temperature"]) == temperature
        ]
        for temperature in temperatures
    }
    computed = {
        temperature: metrics_for(group)
        for temperature, group in grouped.items()
        if group
    }

    lines = [
        "# Homework 1 Non-Determinism Metrics",
        "",
        f"- Model: `{model}`",
        f"- Fixed input: `{case_path.relative_to(PROJECT_ROOT)}`",
        f"- Input SHA-256: `{case_hash}`",
        "- Latency percentiles: linear interpolation using `(n - 1) * p`.",
        "",
        "| Metric | Temp 0.7 | Temp 0.0 |",
        "| --- | --- | --- |",
    ]

    def metric_value(temperature: float, key: str, formatter=str) -> str:
        metric = computed.get(temperature)
        return formatter(metric[key]) if metric else "Pending"

    lines.extend(
        [
            "| Completed runs | "
            f"{metric_value(0.7, 'run_count')} | {metric_value(0.0, 'run_count')} |",
            "| Distinct tag sets | "
            f"{metric_value(0.7, 'distinct_tag_sets')} | {metric_value(0.0, 'distinct_tag_sets')} |",
            "| Tags in all runs | "
            f"{metric_value(0.7, 'tags_in_all_runs', display_tags)} | "
            f"{metric_value(0.0, 'tags_in_all_runs', display_tags)} |",
            "| Tags in exactly 1 run | "
            f"{metric_value(0.7, 'tags_in_exactly_one_run', display_tags)} | "
            f"{metric_value(0.0, 'tags_in_exactly_one_run', display_tags)} |",
            "| Latency p50 / p95 / p99 (ms) | "
            f"{metric_value(0.7, 'latency_p50_ms', lambda value: f'{value:.1f}')} / "
            f"{metric_value(0.7, 'latency_p95_ms', lambda value: f'{value:.1f}')} / "
            f"{metric_value(0.7, 'latency_p99_ms', lambda value: f'{value:.1f}')} | "
            f"{metric_value(0.0, 'latency_p50_ms', lambda value: f'{value:.1f}')} / "
            f"{metric_value(0.0, 'latency_p95_ms', lambda value: f'{value:.1f}')} / "
            f"{metric_value(0.0, 'latency_p99_ms', lambda value: f'{value:.1f}')} |",
            "",
        ]
    )
    metrics_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="reports/hw01/cases/nondeterminism_input.json",
    )
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--runs-per-temperature", type=int, default=20)
    parser.add_argument("--temperatures", type=float, nargs="+", default=[0.7, 0.0])
    parser.add_argument("--output-stem", default="nondeterminism_runs")
    parser.add_argument("--log-name", default="RUN_LOG.txt")
    parser.add_argument("--metrics-name", default="METRICS.md")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()

    if args.runs_per_temperature < 1:
        parser.error("--runs-per-temperature must be at least 1")

    case_path = (PROJECT_ROOT / args.input).resolve()
    case = json.loads(case_path.read_text(encoding="utf-8"))
    title = str(case["title"])
    content = str(case["content"])
    case_hash = input_sha256(case_path)

    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = RAW_ROOT / f"{args.output_stem}.json"
    csv_path = RAW_ROOT / f"{args.output_stem}.csv"
    log_path = REPORT_ROOT / args.log_name
    metrics_path = REPORT_ROOT / args.metrics_name

    if json_path.exists():
        existing_payload = json.loads(json_path.read_text(encoding="utf-8"))
        if existing_payload.get("input_sha256") != case_hash:
            raise ValueError("Existing results use a different fixed input")
        results = list(existing_payload.get("results", []))
    else:
        results = []

    completed = {
        (float(result["temperature"]), int(result["run"]))
        for result in results
    }

    with log_path.open("a", encoding="utf-8") as log:
        log.write(
            f"[{utc_now()}] Experiment invocation: model={args.model}, "
            f"runs_per_temperature={args.runs_per_temperature}, "
            f"temperatures={args.temperatures}, input_sha256={case_hash}\n"
        )
        log.flush()

        for temperature in args.temperatures:
            for run_number in range(1, args.runs_per_temperature + 1):
                key = (float(temperature), run_number)
                if key in completed:
                    print(f"Skipping completed temp={temperature}, run={run_number}", flush=True)
                    continue

                command = [
                    sys.executable,
                    str(PROJECT_ROOT / "code" / "agents_demo.py"),
                    "--model",
                    args.model,
                    "--temperature",
                    str(temperature),
                    "--strict",
                    "--title",
                    title,
                    "--content",
                    content,
                ]
                started_at = utc_now()
                print(
                    f"[{started_at}] Starting temp={temperature}, "
                    f"run={run_number}/{args.runs_per_temperature}",
                    flush=True,
                )
                log.write(
                    f"\n[{started_at}] START temp={temperature}, run={run_number}\n"
                    f"COMMAND: {json.dumps(command)}\n"
                )
                log.flush()

                start = time.perf_counter()
                process = subprocess.run(
                    command,
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=args.timeout_seconds,
                    check=False,
                )
                latency_ms = round((time.perf_counter() - start) * 1000)

                log.write(process.stdout)
                if process.stderr:
                    log.write("\nSTDERR:\n" + process.stderr)

                if process.returncode != 0:
                    log.write(
                        f"\n[{utc_now()}] FAILED returncode={process.returncode}, "
                        f"latency_ms={latency_ms}\n"
                    )
                    log.flush()
                    raise RuntimeError(
                        f"agents_demo.py failed for temp={temperature}, run={run_number}"
                    )

                package = parse_publish_package(process.stdout)
                final = package.get("agents", {}).get("final", {})
                tags = final.get("tags", [])
                summary = final.get("summary", "")
                if not isinstance(tags, list) or len(tags) != 3:
                    raise ValueError("Final output did not contain exactly three tags")

                result = {
                    "temperature": float(temperature),
                    "run": run_number,
                    "timestamp_utc": started_at,
                    "latency_ms": latency_ms,
                    "tags": [str(tag) for tag in tags],
                    "summary": str(summary),
                }
                results.append(result)
                completed.add(key)
                results.sort(key=lambda item: (-float(item["temperature"]), int(item["run"])))
                save_raw_results(
                    results,
                    json_path,
                    csv_path,
                    args.model,
                    case_path,
                    case_hash,
                )
                write_metrics(
                    results,
                    args.temperatures,
                    metrics_path,
                    case_path,
                    case_hash,
                    args.model,
                )

                finished_at = utc_now()
                log.write(
                    f"\n[{finished_at}] COMPLETE temp={temperature}, run={run_number}, "
                    f"latency_ms={latency_ms}, tags={json.dumps(tags)}\n"
                )
                log.flush()
                print(
                    f"[{finished_at}] Completed temp={temperature}, run={run_number}; "
                    f"latency={latency_ms} ms; tags={tags}",
                    flush=True,
                )

    print(f"Saved JSON results to {json_path}")
    print(f"Saved CSV results to {csv_path}")
    print(f"Saved metrics to {metrics_path}")


if __name__ == "__main__":
    main()
