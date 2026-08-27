#!/bin/sh
set -eu

fail() {
  printf 'HATA: %s\n' "$1" >&2
  exit 1
}

[ "$#" -eq 2 ] || fail "Kullanım: $0 WAREHOUSE_KLASORU 'SQL SORGUSU'"

project_root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
warehouse=$1
query=$2
case "$warehouse" in
  /*) ;;
  *) warehouse="$project_root/$warehouse" ;;
esac

[ -d "$warehouse" ] || fail "Iceberg warehouse bulunamadı: $warehouse"
mkdir -p "$project_root/spark/.ivy2"
warehouse_dir=$(dirname "$warehouse")
warehouse_name=$(basename "$warehouse")
iceberg_package=org.apache.iceberg:iceberg-spark-runtime-4.0_2.13:1.11.0

exec docker run --rm \
  --cpus=2 \
  --memory=3g \
  -e HOME=/tmp \
  -e SPARK_LOCAL_DIRS=/tmp/spark \
  -e SPARK_SUBMIT_OPTS=-Duser.home=/tmp \
  -v "$project_root/spark/.ivy2:/tmp/.ivy2" \
  -v "$warehouse_dir:/warehouse-parent:ro" \
  --entrypoint /opt/spark/bin/spark-sql \
  apache/spark@sha256:acfe7e06e95dd13aa32ee03c464766900d52fba15f58e421f8e1213ec041bb94 \
  --packages "$iceberg_package" \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  --master 'local[2]' \
  --conf spark.driver.memory=2g \
  --conf spark.sql.catalogImplementation=in-memory \
  --conf spark.sql.session.timeZone=UTC \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.local=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.local.type=hadoop \
  --conf spark.sql.catalog.local.warehouse="/warehouse-parent/$warehouse_name" \
  --conf spark.sql.defaultCatalog=local \
  -e "$query"
