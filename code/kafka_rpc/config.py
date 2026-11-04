# SID4 1421 personal config for HW8
import os

SID4 = 1421
PORT_BASE = 8521
PREFIX = "s1421"
SEED = 1421
VERIFY_SEED = 261421
DOMAIN_ID = 5

# docker compose sets KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

REQUEST_TOPIC = f"{PREFIX}_entity_requests"
RESPONSE_TOPIC = f"{PREFIX}_entity_responses"
TIMEOUT_SECONDS = 10

INBOX_TOPIC = f"{PREFIX}_inbox"
TASKS_TOPIC = f"{PREFIX}_tasks"
DRAFTS_TOPIC = f"{PREFIX}_drafts"
FINAL_TOPIC = f"{PREFIX}_final"
DEAD_LETTER_TOPIC = f"{PREFIX}_dead_letter"

OLLAMA_MODEL = "qwen3:8b"
