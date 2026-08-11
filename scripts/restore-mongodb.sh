#!/bin/sh
set -eu

archive=${1:-}
mode=${2:-}
confirmation=${3:-}
if [ -z "$archive" ] || [ ! -f "$archive" ]; then
  printf 'Kullanım: %s YEDEK.jsonl.gz [--replace --yes]\n' "$0" >&2
  exit 2
fi
case "$archive" in
  /*) ;;
  *) archive="$PWD/$archive" ;;
esac

project_root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
cd "$project_root"

if docker compose ps --services --status running consumer | grep -q '^consumer$'; then
  printf 'HATA: MongoDB consumer çalışıyor; yarış durumunu önlemek için restore yapılmadı.\n' >&2
  printf 'Önce: docker compose stop consumer\n' >&2
  exit 1
fi

document_count=$(docker compose run --rm --no-deps -T consumer \
  python /app/mongodb_transfer.py count | tail -n 1)
case "$document_count" in
  ''|*[!0-9]*)
    printf 'HATA: Hedef database belge sayısı güvenli biçimde okunamadı.\n' >&2
    exit 1
    ;;
esac

set --
if [ "$document_count" != "0" ]; then
  if [ "$mode" != "--replace" ] || [ "$confirmation" != "--yes" ]; then
    printf 'HATA: Hedef flightdb boş değil (%s belge). Değişiklik yapılmadı.\n' "$document_count" >&2
    printf 'Bilinçli değiştirme için: %s %s --replace --yes\n' "$0" "$archive" >&2
    exit 1
  fi
  set -- --replace
fi

docker compose run --rm --no-deps -T consumer \
  python /app/mongodb_transfer.py import "$@" < "$archive"

printf 'MongoDB uygulama verisi geri yüklendi. Kafka/offset verisi taşınmadı.\n'
