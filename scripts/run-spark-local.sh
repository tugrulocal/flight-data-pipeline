#!/bin/sh
set -eu

fail() {
  printf 'HATA: %s\n' "$1" >&2
  exit 1
}

[ "$#" -eq 2 ] || fail "Kullanım: $0 GIRDİ.jsonl.gz YENI_CIKTI_KLASORU"

project_root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
input=$1
output=$2
case "$input" in
  /*) ;;
  *) input="$project_root/$input" ;;
esac
case "$output" in
  /*) ;;
  *) output="$project_root/$output" ;;
esac

[ -f "$input" ] || fail "Girdi dosyası bulunamadı: $input"
[ ! -e "$output" ] || fail "Çıktı zaten var; üzerine yazılmadı: $output"
mkdir -p "$(dirname "$output")"

input_dir=$(dirname "$input")
input_name=$(basename "$input")
output_dir=$(dirname "$output")
output_name=$(basename "$output")
max_velocity_mps=${SPARK_MAX_VELOCITY_MPS:-400}
max_observation_lag_minutes=${SPARK_MAX_OBSERVATION_LAG_MINUTES:-20}

# local[2] tek Spark sürecidir; Kubernetes'e executor veya pod oluşturmaz.
exec docker run --rm \
  --cpus=2 \
  --memory=3g \
  -e HOME=/tmp \
  -e SPARK_LOCAL_DIRS=/tmp/spark \
  -e SPARK_SUBMIT_OPTS=-Duser.home=/tmp \
  -v "$project_root/spark:/opt/flight-spark:ro" \
  -v "$input_dir:/input:ro" \
  -v "$output_dir:/output" \
  --entrypoint /opt/spark/bin/spark-submit \
  apache/spark@sha256:acfe7e06e95dd13aa32ee03c464766900d52fba15f58e421f8e1213ec041bb94 \
  --master 'local[2]' \
  --conf spark.driver.memory=2g \
  --conf spark.sql.shuffle.partitions=2 \
  --conf spark.sql.session.timeZone=UTC \
  /opt/flight-spark/jobs/hourly_traffic_report.py \
  --input "/input/$input_name" \
  --output "/output/$output_name" \
  --max-velocity-mps "$max_velocity_mps" \
  --max-observation-lag-minutes "$max_observation_lag_minutes"
