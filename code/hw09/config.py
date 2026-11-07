# SID4 1421 - same as earlier homeworks
import os

SID4 = 1421
PORT_BASE = 8521
PREFIX = "s1421"
SEED = 1421
VERIFY_SEED = 261421
DOMAIN_ID = 5

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# semantic cache
DEFAULT_THRESHOLD = 0.85
EMBED_MODEL = os.getenv("HW9_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# cost model dollars (made up but justified in METRICS)
MISS_COST = 0.02  # extra llm / agent path cost
FALSE_HIT_COST = 0.50  # support / wrong-answer cleanup
