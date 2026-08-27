#!/bin/sh
set -eu

fail() {
  printf 'HATA: %s\n' "$1" >&2
  exit 1
}

project_root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
namespace=${K8S_NAMESPACE:-flight-data-pipeline}
pod=${MONGODB_POD:-mongodb-0}
default_output="$project_root/spark/data/raw_positions-$(date -u +%Y%m%dT%H%M%SZ).jsonl.gz"
since_ingested_at=

if [ "${1:-}" = "--since-ingested-at" ]; then
  [ "$#" -eq 2 ] || [ "$#" -eq 3 ] || fail "Kullanım: $0 [--since-ingested-at UTC_ISO_Z] [CIKTI.jsonl.gz]"
  since_ingested_at=$2
  output=${3:-"$default_output"}
  printf '%s' "$since_ingested_at" | /usr/bin/grep -Eq \
    '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z$' \
    || fail "since-ingested-at UTC ISO biçiminde olmalı (ör. 2026-08-26T11:42:00.000Z)"
else
  [ "$#" -le 1 ] || fail "Kullanım: $0 [--since-ingested-at UTC_ISO_Z] [CIKTI.jsonl.gz]"
  output=${1:-"$default_output"}
fi

case "$output" in
  /*) ;;
  *) output="$project_root/$output" ;;
esac

[ ! -e "$output" ] || fail "Hedef dosya zaten var; üzerine yazılmadı: $output"
mkdir -p "$(dirname "$output")"
temporary=$(mktemp "${output}.tmp.XXXXXX")
compressed_temporary=$(mktemp "${output}.tmp.gz.XXXXXX")
cleanup() {
  [ ! -f "$temporary" ] || find "$temporary" -delete
  [ ! -f "$compressed_temporary" ] || find "$compressed_temporary" -delete
}
trap cleanup EXIT INT TERM

kubectl get pod "$pod" --namespace "$namespace" >/dev/null \
  || fail "MongoDB pod'u bulunamadı: $namespace/$pod"

# Canonical Extended JSON tarih/sayı tiplerini korur; Spark işi bu biçimi okur.
# since_ingested_at verilirse MongoDB yalnız yeni zaman aralığını okur. Bu değer
# regex ile doğrulandığı için mongosh ifadesine güvenle eklenebilir.
if [ -n "$since_ingested_at" ]; then
  mongo_filter="{ingested_at: {\$gt: ISODate('$since_ingested_at')}}"
  printf 'MongoDB export filtresi: ingested_at > %s\n' "$since_ingested_at"
else
  mongo_filter='{}'
  printf 'MongoDB export filtresi: tüm raw_positions\n'
fi
kubectl exec --namespace "$namespace" "$pod" -- \
  mongosh --quiet flightdb --eval \
  "db.raw_positions.find($mongo_filter).batchSize(1000).forEach(function (doc) { print(EJSON.stringify(doc, { relaxed: false })); });" \
  > "$temporary" || fail "MongoDB raw_positions export başarısız"

[ -s "$temporary" ] || fail "Export boş çıktı üretti"
gzip -9 < "$temporary" > "$compressed_temporary"
mv "$compressed_temporary" "$output"
trap - EXIT INT TERM
find "$temporary" -delete

printf 'Spark için salt-okunur raw_positions export oluşturuldu: %s\n' "$output"
printf 'Bu dosya Git tarafından yok sayılır; MongoDB, Kafka ve canlı akış değiştirilmedi.\n'
