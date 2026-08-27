#!/bin/sh
set -eu

fail() {
  printf 'HATA: %s\n' "$1" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Kullanım:
  scripts/refresh-iceberg-dashboard.sh --dry-run [WAREHOUSE_KLASORU]
  scripts/refresh-iceberg-dashboard.sh --apply [WAREHOUSE_KLASORU]

Varsayılan warehouse: spark/warehouse/validation-real-data-stale

--dry-run: MongoDB'den salt-okunur export alır ve Bronze'a kaç yeni event_id
             ekleneceğini gösterir. Iceberg ve rapora yazmaz.
--apply:   Export -> Bronze -> Silver/Rejected -> Gold -> HTML raporu sırasıyla
             çalıştırır. Bir adım hata verirse sonraki adıma geçmez.
EOF
}

[ "$#" -ge 1 ] && [ "$#" -le 2 ] || {
  usage >&2
  exit 1
}

mode=$1
case "$mode" in
  --dry-run|--apply) ;;
  -h|--help) usage; exit 0 ;;
  *) fail "İlk parametre --dry-run veya --apply olmalı." ;;
esac

project_root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
warehouse=${2:-spark/warehouse/validation-real-data-stale}
case "$warehouse" in
  /*) ;;
  *) warehouse="$project_root/$warehouse" ;;
esac
[ -d "$warehouse" ] || fail "Iceberg warehouse bulunamadı: $warehouse"

batch_id=$(date -u +%Y%m%dT%H%M%SZ)
export_file="$project_root/spark/data/raw_positions-${batch_id}-dashboard.jsonl.gz"
report_file="$project_root/spark/reports/iceberg-dashboard-${batch_id}.html"

printf 'Iceberg dashboard batch başladı: %s\n' "$batch_id"
printf 'Warehouse: %s\n' "$warehouse"
printf '\n[1/6] Bronze watermark ve 5 dakikalık overlap\n'
watermark_output=$("$project_root/scripts/read-iceberg-bronze-watermark.sh" "$warehouse")
bronze_watermark=$(printf '%s\n' "$watermark_output" | /usr/bin/awk -F= '/^BRONZE_WATERMARK=/{value=$2} END{print value}')
export_since=$(printf '%s\n' "$watermark_output" | /usr/bin/awk -F= '/^EXPORT_SINCE=/{value=$2} END{print value}')
[ -n "$bronze_watermark" ] || fail "Bronze watermark Spark çıktısından okunamadı."
[ -n "$export_since" ] || fail "Incremental export başlangıcı Spark çıktısından okunamadı."
printf 'Bronze watermark: %s\n' "$bronze_watermark"
printf 'MongoDB incremental export başlangıcı: %s\n' "$export_since"

printf '\n[2/6] MongoDB raw_positions salt-okunur incremental export\n'
"$project_root/scripts/export-spark-raw-positions.sh" \
  --since-ingested-at "$export_since" "$export_file"

printf '\n[3/6] Bronze yeni event_id kontrolü\n'
"$project_root/scripts/inspect-iceberg-batch-refresh.sh" "$export_file" "$warehouse"

if [ "$mode" = "--dry-run" ]; then
  printf '\nDry-run tamamlandı. Iceberg tabloları ve HTML raporu değiştirilmedi.\n'
  printf 'Gerçek yenileme için: scripts/refresh-iceberg-dashboard.sh --apply %s\n' "$warehouse"
  exit 0
fi

printf '\n[4/6] Bronze append\n'
"$project_root/scripts/apply-iceberg-bronze-batch-refresh.sh" "$export_file" "$warehouse"

printf '\n[5/6] Silver/Rejected sınıflandırma ve Gold yenileme\n'
"$project_root/scripts/apply-iceberg-silver-refresh.sh" "$warehouse"
"$project_root/scripts/apply-iceberg-gold-refresh.sh" "$warehouse"

printf '\n[6/6] Güncel Gold tablolarından HTML raporu\n'
"$project_root/scripts/generate-iceberg-report.sh" "$warehouse" "$report_file"

printf '\nBaşarılı: Güncel rapor hazır: %s\n' "$report_file"
printf 'Rapor statiktir; bir sonraki --apply çalıştırması yeni isimli bir rapor üretir.\n'
