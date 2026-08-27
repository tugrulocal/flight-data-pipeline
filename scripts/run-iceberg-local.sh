#!/bin/sh
set -eu

fail() {
  printf 'HATA: %s\n' "$1" >&2
  exit 1
}

[ "$#" -eq 2 ] || fail "Kullanım: $0 GIRDİ.jsonl.gz YENI_WAREHOUSE_KLASORU"

project_root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
input=$1
warehouse=$2
case "$input" in
  /*) ;;
  *) input="$project_root/$input" ;;
esac
case "$warehouse" in
  /*) ;;
  *) warehouse="$project_root/$warehouse" ;;
esac

[ -f "$input" ] || fail "Girdi dosyası bulunamadı: $input"
[ ! -e "$warehouse" ] || fail "Warehouse zaten var; mevcut Iceberg tabloları korunuyor: $warehouse"
mkdir -p "$(dirname "$warehouse")" "$project_root/spark/.ivy2"

input_dir=$(dirname "$input")
input_name=$(basename "$input")
warehouse_dir=$(dirname "$warehouse")
warehouse_name=$(basename "$warehouse")
max_velocity_mps=${SPARK_MAX_VELOCITY_MPS:-400}
max_observation_lag_minutes=${SPARK_MAX_OBSERVATION_LAG_MINUTES:-20}
iceberg_package=org.apache.iceberg:iceberg-spark-runtime-4.0_2.13:1.11.0

# local[2] tek Spark sürecidir. Iceberg Hadoop Catalog metadata/data dosyalarını
# yalnız mount edilen warehouse altında tutar; Kubernetes'e kaynak oluşturmaz.
exec docker run --rm \
  --cpus=2 \
  --memory=3g \
  -e HOME=/tmp \
  -e SPARK_LOCAL_DIRS=/tmp/spark \
  -e SPARK_SUBMIT_OPTS=-Duser.home=/tmp \
  -v "$project_root/spark:/opt/flight-spark:ro" \
  -v "$project_root/spark/.ivy2:/tmp/.ivy2" \
  -v "$input_dir:/input:ro" \
  -v "$warehouse_dir:/warehouse-parent" \
  --entrypoint /opt/spark/bin/spark-submit \
  apache/spark@sha256:acfe7e06e95dd13aa32ee03c464766900d52fba15f58e421f8e1213ec041bb94 \
  --packages "$iceberg_package" \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  --master 'local[2]' \
  --conf spark.driver.memory=2g \
  --conf spark.sql.shuffle.partitions=2 \
  --conf spark.sql.catalogImplementation=in-memory \
  --conf spark.sql.session.timeZone=UTC \
  /opt/flight-spark/jobs/iceberg_positions.py \
  --input "/input/$input_name" \
  --warehouse "/warehouse-parent/$warehouse_name" \
  --max-velocity-mps "$max_velocity_mps" \
  --max-observation-lag-minutes "$max_observation_lag_minutes"
