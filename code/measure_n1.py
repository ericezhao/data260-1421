"""Measure the N+1 list endpoints for HW4 Part 3.

For each version and page size, sends 30 requests and records the SQL statement
count (X-SQL-Count header) and client-side latency.

The backend must already be running:  python main.py
Run:  python measure_n1.py                      (naive and fixed)
      python measure_n1.py --versions naive     (one version only)
"""
import argparse
import csv
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8521"
EMAIL = "eric.zhao@sjsu.edu"
PASSWORD = "password"
PAGE_SIZES = [10, 50, 200]
REQUESTS_PER_SIZE = 30
WARMUP_REQUESTS = 3

RAW_DIR = Path(__file__).resolve().parent.parent / "reports" / "hw04" / "raw"


def percentile(values, p):
    ordered = sorted(values)
    k = (len(ordered) - 1) * p / 100
    low = int(k)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (k - low)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions", nargs="+", default=["naive", "fixed"])
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = []

    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD}).raise_for_status()

        for version in args.versions:
            url = f"/api/inspections/{version}"
            for size in PAGE_SIZES:
                # warm-up requests are not recorded (connection pool, caches)
                for _ in range(WARMUP_REQUESTS):
                    client.get(url, params={"limit": size}).raise_for_status()

                for i in range(1, REQUESTS_PER_SIZE + 1):
                    start = time.perf_counter()
                    res = client.get(url, params={"limit": size})
                    latency_ms = (time.perf_counter() - start) * 1000
                    res.raise_for_status()
                    rows.append(
                        {
                            "version": version,
                            "page_size": size,
                            "request_no": i,
                            "status": res.status_code,
                            "records": len(res.json()),
                            "sql_count": int(res.headers["X-SQL-Count"]),
                            "latency_ms": round(latency_ms, 3),
                        }
                    )

    raw_path = RAW_DIR / "n1_requests.csv"
    with raw_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    summary = []
    for size in PAGE_SIZES:
        for version in args.versions:
            group = [r for r in rows if r["version"] == version and r["page_size"] == size]
            latencies = [r["latency_ms"] for r in group]
            summary.append(
                {
                    "page_size": size,
                    "version": version,
                    "sql_per_request": group[0]["sql_count"],
                    "p50_ms": round(percentile(latencies, 50), 2),
                    "p95_ms": round(percentile(latencies, 95), 2),
                    "p99_ms": round(percentile(latencies, 99), 2),
                }
            )

    summary_path = RAW_DIR / "n1_summary.csv"
    with summary_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)

    print(f"{len(rows)} requests -> {raw_path}")
    print(f"summary -> {summary_path}\n")
    print("| Page size | Version | SQL stmts/req | p50 (ms) | p95 (ms) | p99 (ms) |")
    print("|---|---|---|---|---|---|")
    for s in summary:
        print(
            f"| {s['page_size']} | {s['version']} | {s['sql_per_request']} "
            f"| {s['p50_ms']} | {s['p95_ms']} | {s['p99_ms']} |"
        )


if __name__ == "__main__":
    main()
