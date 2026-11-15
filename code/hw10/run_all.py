#!/usr/bin/env python3
# run evidence scripts in order
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV = os.environ.copy()
ENV["PYTHONPATH"] = os.pathsep.join(
    [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps"), ENV.get("PYTHONPATH", "")]
)


def run(mod, extra=None):
    env = ENV.copy()
    if extra:
        env.update(extra)
    print("\n=====", mod, "=====")
    r = subprocess.run([sys.executable, "-m", mod], cwd=str(ROOT), env=env)
    if r.returncode != 0:
        raise SystemExit(f"{mod} failed rc={r.returncode}")


def main():
    run("hw10.run_part4_traces")
    run("hw10.run_part2_eval")
    run("hw10.run_part3_judge")
    run(
        "hw10.run_part4_latency",
        extra={"HW10_MOCK_LLM": "1", "HW8_MOCK_LLM": "1", "HW10_MOCK_JUDGE": "1"},
    )
    sys.path[:0] = [str(ROOT), str(ROOT / "code"), str(ROOT / ".deps")]
    from hw10.ops_summary import build_summary

    s = build_summary()
    print("summary requests=", s.get("n_requests"), "hit_rate=", s.get("cache_hit_rate"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
