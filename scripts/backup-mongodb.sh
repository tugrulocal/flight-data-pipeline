#!/bin/sh
set -eu

fail() {
  printf 'HATA: %s\n' "$1" >&2
  exit 1
}

output=${1:-flightdb-$(date -u +%Y%m%dT%H%M%SZ).jsonl.gz}
case "$output" in
  /*) ;;
  *) output="$PWD/$output" ;;
esac
[ ! -e "$output" ] || fail "Hedef dosya zaten var; üzerine yazılmadı: $output"
[ -d "$(dirname "$output")" ] || fail "Hedef klasör bulunamadı: $(dirname "$output")"

project_root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
cd "$project_root"

umask 077
temporary=$(mktemp "${output}.tmp.XXXXXX")
cleanup() {
  [ ! -f "$temporary" ] || find "$temporary" -delete
}
trap cleanup EXIT INT TERM

docker compose run --rm --no-deps -T consumer \
  python /app/mongodb_transfer.py export \
  > "$temporary" || fail "MongoDB export başarısız; yarım arşiv silindi."

[ -s "$temporary" ] || fail "MongoDB export boş arşiv üretti."
mv "$temporary" "$output"
trap - EXIT INT TERM

printf 'MongoDB uygulama yedeği oluşturuldu: %s\n' "$output"
printf 'Kafka verisi ve consumer offsetleri bu yedeğe dahil değildir.\n'
