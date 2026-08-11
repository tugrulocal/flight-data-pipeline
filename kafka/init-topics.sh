#!/bin/sh
set -eu

bootstrap_server="${KAFKA_BOOTSTRAP_SERVERS:-kafka:29092}"
raw_topic="${KAFKA_TOPIC:-aircraft.positions.raw.v1}"
dlq_topic="${KAFKA_DLQ_TOPIC:-aircraft.positions.dlq.v1}"
raw_retention_ms="${KAFKA_RAW_RETENTION_MS:-172800000}"
raw_retention_bytes="${KAFKA_RAW_RETENTION_BYTES:-10737418240}"
dlq_retention_ms="${KAFKA_DLQ_RETENTION_MS:-2592000000}"
dlq_retention_bytes="${KAFKA_DLQ_RETENTION_BYTES:-1073741824}"
topics_bin=/opt/kafka/bin/kafka-topics.sh
configs_bin=/opt/kafka/bin/kafka-configs.sh

require_positive_integer() {
  case "$2" in
    ''|*[!0-9]*|0)
      printf '%s pozitif tam sayı olmalı: %s\n' "$1" "$2" >&2
      exit 2
      ;;
  esac
}

require_positive_integer KAFKA_RAW_RETENTION_MS "$raw_retention_ms"
require_positive_integer KAFKA_RAW_RETENTION_BYTES "$raw_retention_bytes"
require_positive_integer KAFKA_DLQ_RETENTION_MS "$dlq_retention_ms"
require_positive_integer KAFKA_DLQ_RETENTION_BYTES "$dlq_retention_bytes"

create_topic() {
  "$topics_bin" \
    --bootstrap-server "$bootstrap_server" \
    --create \
    --if-not-exists \
    --topic "$1" \
    --partitions 1 \
    --replication-factor 1
}

configure_topic() {
  "$configs_bin" \
    --bootstrap-server "$bootstrap_server" \
    --entity-type topics \
    --entity-name "$1" \
    --alter \
    --add-config "cleanup.policy=delete,retention.ms=$2,retention.bytes=$3"
}

verify_topic_config() {
  config=$(
    "$configs_bin" \
      --bootstrap-server "$bootstrap_server" \
      --entity-type topics \
      --entity-name "$1" \
      --describe
  )

  for expected in \
    "cleanup.policy=delete" \
    "retention.ms=$2" \
    "retention.bytes=$3"
  do
    case "$config" in
      *"$expected"*) ;;
      *)
        printf '%s config doğrulaması başarısız: %s\n' "$1" "$expected" >&2
        exit 1
        ;;
    esac
  done
}

create_topic "$raw_topic"
configure_topic "$raw_topic" "$raw_retention_ms" "$raw_retention_bytes"
verify_topic_config "$raw_topic" "$raw_retention_ms" "$raw_retention_bytes"
create_topic "$dlq_topic"
configure_topic "$dlq_topic" "$dlq_retention_ms" "$dlq_retention_bytes"
verify_topic_config "$dlq_topic" "$dlq_retention_ms" "$dlq_retention_bytes"

"$topics_bin" --bootstrap-server "$bootstrap_server" --describe --topic "$raw_topic"
"$topics_bin" --bootstrap-server "$bootstrap_server" --describe --topic "$dlq_topic"
