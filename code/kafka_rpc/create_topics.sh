#!/usr/bin/env bash
# Create PREFIX-prefixed Kafka topics for HW8 (run after docker compose up).
set -euo pipefail
CONTAINER="${1:-s1421-kafka}"
# Inside the container the PLAINTEXT listener is on 9092.
BOOT="${2:-localhost:9092}"

create() {
  local topic="$1"
  local parts="${2:-1}"
  docker exec "$CONTAINER" /opt/kafka/bin/kafka-topics.sh \
    --create --if-not-exists \
    --topic "$topic" \
    --partitions "$parts" \
    --replication-factor 1 \
    --bootstrap-server "$BOOT"
}

create s1421_entity_requests 1
create s1421_entity_responses 1
create s1421_inbox 1
create s1421_tasks 2
create s1421_drafts 1
create s1421_final 1
create s1421_dead_letter 1

docker exec "$CONTAINER" /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server "$BOOT"
echo "Topics ready"
