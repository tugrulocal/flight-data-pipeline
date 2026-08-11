#!/bin/sh
set -eu

root=$(CDPATH='' cd -- "$(dirname "$0")/../.." && pwd)

dc() {
  docker compose -f "$root/tests/integration/compose.yaml" "$@"
}

kt() {
  # Native broker image yönetim CLI'larını içermez. JVM image yalnız bu izole
  # testte, Kafka protokolünü dışarıdan sınayan geçici bir istemci olarak çalışır.
  dc run --rm --no-deps -T kafka-tools "$@"
}

fail() {
  printf 'Integration HATA: %s\n' "$1" >&2
  exit 1
}

cleanup() {
  # Yalnız sabit isimli izole test projesinin geçici kaynaklarını temizler.
  dc down --volumes --remove-orphans >/dev/null 2>&1 || true
  if [ -n "${backup_probe:-}" ] && [ -f "$backup_probe" ]; then
    find "$backup_probe" -delete
  fi
}
trap cleanup EXIT INT TERM
cleanup

dc up -d --build consumer backend frontend

# Topic init mevcut config'i de beklenen değerlere geri getirmeli.
kt /opt/kafka/bin/kafka-configs.sh \
  --bootstrap-server kafka:29092 \
  --entity-type topics \
  --entity-name aircraft.positions.raw.v1 \
  --alter \
  --add-config retention.ms=9999,retention.bytes=9999 >/dev/null
dc run --rm topic-init >/dev/null
raw_config=$(kt /opt/kafka/bin/kafka-configs.sh \
  --bootstrap-server kafka:29092 \
  --entity-type topics \
  --entity-name aircraft.positions.raw.v1 \
  --describe)
for expected in \
  cleanup.policy=delete \
  retention.ms=60000 \
  retention.bytes=10485760
do
  case "$raw_config" in
    *"$expected"*) ;;
    *) printf '%s\n' "$raw_config"; fail "raw topic config eşleşmedi: $expected" ;;
  esac
done

raw_description=$(kt /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:29092 \
  --describe --topic aircraft.positions.raw.v1)
dlq_description=$(kt /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:29092 \
  --describe --topic aircraft.positions.dlq.v1)
printf '%s' "$raw_description" | grep -q 'PartitionCount: 1' \
  || fail "raw topic partition sayısı 1 değil"
printf '%s' "$dlq_description" | grep -q 'PartitionCount: 1' \
  || fail "DLQ topic partition sayısı 1 değil"

# Kısa ömürlü MongoDB probe gerçekten TTL monitor tarafından silinmeli.
dc exec -T mongodb mongosh --quiet flightdb --eval '
  db.ttl_probe.drop();
  db.ttl_probe.createIndex({expires_at:1},{expireAfterSeconds:1});
  db.ttl_probe.insertOne({expires_at:new Date(Date.now()-10000)});
' >/dev/null
attempt=0
mongo_ttl_count=1
while [ "$attempt" -lt 15 ]; do
  mongo_ttl_count=$(dc exec -T mongodb mongosh --quiet flightdb --eval \
    'print(db.ttl_probe.countDocuments())' | tail -n 1)
  [ "$mongo_ttl_count" = "0" ] && break
  attempt=$((attempt + 1))
  sleep 1
done
[ "$mongo_ttl_count" = "0" ] || fail "Mongo TTL probe silinmedi"

# Kısa ömürlü Kafka probe'da eski segment silinince earliest offset ilerler.
kt /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:29092 \
  --create --topic retention-probe \
  --partitions 1 --replication-factor 1 \
  --config cleanup.policy=delete \
  --config retention.ms=1000 \
  --config segment.ms=1000 \
  --config file.delete.delay.ms=1000 >/dev/null
printf 'first\n' | kt \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:29092 --topic retention-probe >/dev/null
sleep 2
printf 'second\n' | kt \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:29092 --topic retention-probe >/dev/null
sleep 2
printf 'third\n' | kt \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:29092 --topic retention-probe >/dev/null
attempt=0
kafka_earliest=0
while [ "$attempt" -lt 20 ]; do
  kafka_earliest=$(kt /opt/kafka/bin/kafka-get-offsets.sh \
    --bootstrap-server kafka:29092 --topic retention-probe --time -2 \
    | awk -F: '{total += $3} END {print total + 0}')
  [ "$kafka_earliest" -ge 1 ] && break
  attempt=$((attempt + 1))
  sleep 1
done
[ "$kafka_earliest" -ge 1 ] \
  || fail "Kafka retention probe silinmedi; earliest=$kafka_earliest"

observed=$(date -u +%Y-%m-%dT%H:%M:%SZ)
event="{\"schema_version\":1,\"event_id\":\"00000000-0000-4000-8000-000000000001\",\"icao24\":\"4baa12\",\"latitude\":41.0,\"longitude\":29.0,\"on_ground\":null,\"observed_at\":\"$observed\",\"ingested_at\":\"$observed\",\"source\":\"integration\"}"

printf '%s\n%s\nnot-json\n' "$event" "$event" | kt \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:29092 \
  --topic aircraft.positions.raw.v1 >/dev/null

attempt=0
counts="0:0"
dlq=0
while [ "$attempt" -lt 30 ]; do
  counts=$(dc exec -T mongodb mongosh --quiet flightdb --eval \
    'print(db.raw_positions.countDocuments({_id:"00000000-0000-4000-8000-000000000001"}) + ":" + db.live_positions.countDocuments({_id:"4baa12"}))' | tail -n 1)
  dlq=$(kt /opt/kafka/bin/kafka-get-offsets.sh \
    --bootstrap-server kafka:29092 --topic aircraft.positions.dlq.v1 2>/dev/null | awk -F: '{total += $3} END {print total + 0}')
  [ "$counts" = "1:1" ] && [ "$dlq" -ge 1 ] && break
  attempt=$((attempt + 1))
  sleep 1
done

[ "$counts" = "1:1" ] || { dc logs consumer; exit 1; }
[ "$dlq" -ge 1 ] || { dc logs consumer; exit 1; }

older_event="{\"schema_version\":1,\"event_id\":\"00000000-0000-4000-8000-000000000003\",\"icao24\":\"4baa12\",\"latitude\":1.0,\"longitude\":1.0,\"on_ground\":true,\"observed_at\":\"2000-01-01T00:00:00Z\",\"ingested_at\":\"$observed\",\"source\":\"integration\"}"
printf '%s\n' "$older_event" | kt \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:29092 --topic aircraft.positions.raw.v1 >/dev/null
attempt=0
older_raw=0
while [ "$attempt" -lt 20 ]; do
  older_raw=$(dc exec -T mongodb mongosh --quiet flightdb --eval \
    'print(db.raw_positions.countDocuments({_id:"00000000-0000-4000-8000-000000000003"}))' | tail -n 1)
  [ "$older_raw" = "1" ] && break
  attempt=$((attempt + 1))
  sleep 1
done
[ "$older_raw" = "1" ] || { dc logs consumer; exit 1; }
live_observed=$(dc exec -T mongodb mongosh --quiet flightdb --eval \
  'const d=db.live_positions.findOne({_id:"4baa12"}); print(d ? d.observed_at.toISOString() : "")' | tail -n 1)
case "$live_observed" in 2000-*) dc logs consumer; exit 1 ;; esac

api_payload=$(dc exec -T frontend wget -qO- 'http://127.0.0.1/api/aircraft?limit=5')
printf '%s' "$api_payload" | grep -q '"window_minutes":10' || exit 1
printf '%s' "$api_payload" | grep -q '"truncated":false' || exit 1
health_payload=$(dc exec -T frontend wget -qO- http://127.0.0.1/health)
printf '%s' "$health_payload" | grep -q '"version":"integration"' || exit 1
ws_ready=$(dc exec -T backend python -c 'from websockets.sync.client import connect; c=connect("ws://frontend/ws/aircraft"); print(c.recv(timeout=5)); c.close()')
printf '%s' "$ws_ready" | grep -q 'connection.ready' || exit 1

# Backend yeni bir container/IP ile döndüğünde Nginx Docker DNS'ini yeniden
# çözmeli; REST ve WebSocket eski IP'de takılıp 502 üretmemeli.
dc up -d --force-recreate backend >/dev/null
attempt=0
proxy_recovered=0
while [ "$attempt" -lt 20 ]; do
  if dc exec -T frontend wget -qO- http://127.0.0.1/health \
    | grep -q '"version":"integration"'; then
    proxy_recovered=1
    break
  fi
  attempt=$((attempt + 1))
  sleep 1
done
[ "$proxy_recovered" = "1" ] || { dc logs frontend backend; fail "Nginx backend IP değişiminden sonra toparlanmadı"; }
ws_ready=$(dc exec -T backend python -c 'from websockets.sync.client import connect; c=connect("ws://frontend/ws/aircraft"); print(c.recv(timeout=5)); c.close()')
printf '%s' "$ws_ready" | grep -q 'connection.ready' \
  || fail "WebSocket backend yeniden oluşturulduktan sonra toparlanmadı"

lag=$(kt /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server kafka:29092 --describe --group flight-mongodb-writer-v1 2>/dev/null \
  | awk 'NR > 1 && $6 ~ /^[0-9]+$/ {total += $6} END {print total + 0}')
[ "$lag" = "0" ] || { dc logs consumer; exit 1; }

# $gte MongoDB operatörüdür, shell değişkeni değildir.
# shellcheck disable=SC2016
plan=$(dc exec -T mongodb mongosh --quiet flightdb --eval \
  'printjson(db.live_positions.find({observed_at:{$gte:new Date(0)}}).sort({observed_at:-1}).explain().queryPlanner.winningPlan)' | tr -d '\n')
printf '%s' "$plan" | grep -q IXSCAN || { printf '%s\n' "$plan"; exit 1; }

ttl_indexes=$(dc exec -T mongodb mongosh --quiet flightdb --eval '
  printjson({
    raw: db.raw_positions.getIndexes().find(i => i.name === "idx_raw_ingested_at_ttl"),
    live: db.live_positions.getIndexes().find(i => i.name === "idx_live_ingested_at_ttl")
  })
' | tr -d '\n ')
printf '%s' "$ttl_indexes" | grep -q 'ingested_at:1' \
  || fail "TTL index alanı ingested_at değil"
printf '%s' "$ttl_indexes" | grep -q 'expireAfterSeconds:172800' \
  || fail "raw TTL 48 saat değil"
printf '%s' "$ttl_indexes" | grep -q 'expireAfterSeconds:604800' \
  || fail "live TTL 7 gün değil"

# Gerçek Extended JSON export/import yalnız izole test database'inde sınanır.
backup_probe=$(mktemp /tmp/flightdb-integration.XXXXXX.jsonl.gz)
find "$backup_probe" -delete
expected_restore_counts=$(dc exec -T mongodb mongosh --quiet flightdb --eval \
  'print(db.raw_positions.countDocuments() + ":" + db.live_positions.countDocuments())' | tail -n 1)
COMPOSE_FILE="$root/tests/integration/compose.yaml" \
  "$root/scripts/backup-mongodb.sh" "$backup_probe" >/dev/null
dc stop consumer >/dev/null
dc exec -T mongodb mongosh --quiet flightdb --eval 'db.dropDatabase()' >/dev/null
COMPOSE_FILE="$root/tests/integration/compose.yaml" \
  "$root/scripts/restore-mongodb.sh" "$backup_probe" >/dev/null
actual_restore_counts=$(dc exec -T mongodb mongosh --quiet flightdb --eval \
  'print(db.raw_positions.countDocuments() + ":" + db.live_positions.countDocuments())' | tail -n 1)
[ "$actual_restore_counts" = "$expected_restore_counts" ] \
  || fail "Backup/restore sayımı eşleşmedi: beklenen=$expected_restore_counts gerçek=$actual_restore_counts"
dc start consumer >/dev/null

# Geçerli mesaj Mongo kesintisinde DLQ'ya gitmemeli ve offset ilerlememeli.
dc stop mongodb >/dev/null
outage_event="{\"schema_version\":1,\"event_id\":\"00000000-0000-4000-8000-000000000002\",\"icao24\":\"4baa14\",\"latitude\":40.0,\"longitude\":30.0,\"on_ground\":false,\"observed_at\":\"$observed\",\"ingested_at\":\"$observed\",\"source\":\"integration\"}"
printf '%s\n' "$outage_event" | kt \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:29092 --topic aircraft.positions.raw.v1 >/dev/null
sleep 5
dlq_during_outage=$(kt /opt/kafka/bin/kafka-get-offsets.sh \
  --bootstrap-server kafka:29092 --topic aircraft.positions.dlq.v1 2>/dev/null | awk -F: '{total += $3} END {print total + 0}')
[ "$dlq_during_outage" = "$dlq" ] || { dc logs consumer; exit 1; }
lag_during_outage=$(kt /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server kafka:29092 --describe --group flight-mongodb-writer-v1 2>/dev/null \
  | awk 'NR > 1 && $6 ~ /^[0-9]+$/ {total += $6} END {print total + 0}')
[ "$lag_during_outage" -ge 1 ] || { dc logs consumer; exit 1; }

dc start mongodb >/dev/null
attempt=0
recovered=0
while [ "$attempt" -lt 45 ]; do
  recovered=$(dc exec -T mongodb mongosh --quiet flightdb --eval \
    'print(db.raw_positions.countDocuments({_id:"00000000-0000-4000-8000-000000000002"}))' 2>/dev/null | tail -n 1 || true)
  [ "$recovered" = "1" ] && break
  attempt=$((attempt + 1))
  sleep 1
done
[ "$recovered" = "1" ] || { dc logs consumer; exit 1; }

attempt=0
recovered_lag=-1
while [ "$attempt" -lt 20 ]; do
  recovered_lag=$(kt /opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server kafka:29092 --describe --group flight-mongodb-writer-v1 2>/dev/null \
    | awk 'NR > 1 && $6 ~ /^[0-9]+$/ {total += $6} END {print total + 0}')
  [ "$recovered_lag" = "0" ] && break
  attempt=$((attempt + 1))
  sleep 1
done
[ "$recovered_lag" = "0" ] || { dc logs consumer; exit 1; }

printf 'Integration başarılı: duplicate raw=1, live=1, dlq=%s, ilk lag=%s, kesinti lag=%s, recovery lag=%s, Mongo recovery=1, backup/restore=evet, IXSCAN=evet, Mongo TTL=evet, Kafka retention earliest=%s\n' \
  "$dlq" "$lag" "$lag_during_outage" "$recovered_lag" "$kafka_earliest"
