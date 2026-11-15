# SID4 1421 - HW10
import os
from pathlib import Path

SID4 = 1421
PORT_BASE = 8521
PREFIX = "s1421"
SEED = 1421
VERIFY_SEED = 261421
DOMAIN_ID = 5

ROOT = Path(__file__).resolve().parents[2]
HW10 = Path(__file__).resolve().parent
REPORTS = ROOT / "reports" / "hw10"
RAW = REPORTS / "raw"
SPANS_DIR = RAW / "spans"
MESSAGES_DIR = RAW / "messages"
TRACES_DIR = RAW / "traces"
EVAL_RESULTS_DIR = RAW / "eval"

JUDGE_MODEL = os.getenv("HW10_JUDGE_MODEL", "qwen3:8b")
GEN_MODEL = os.getenv("HW10_GEN_MODEL", "qwen3:8b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
JUDGE_TIMEOUT_SEC = float(os.getenv("HW10_JUDGE_TIMEOUT", "60"))

SCORE_MIN = 1
SCORE_MAX = 5

DATA_DIR = HW10 / "data"
EVAL_CASES_JSON = DATA_DIR / "eval_cases.json"
HUMAN_LABELS_CSV = DATA_DIR / "human_labels.csv"
JUDGE_REPEAT_N = 3

REPORTS_DIR = REPORTS
LATENCY_JSON = RAW / "latency_50_miss.json"
JUDGE_METRICS_JSON = RAW / "judge_metrics.json"
TRACE_INDEX_JSON = RAW / "trace_index.json"
SUMMARY_JSON = RAW / "summary_metrics.json"
