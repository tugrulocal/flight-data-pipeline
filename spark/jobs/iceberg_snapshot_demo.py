"""Iceberg snapshot ve time-travel'i küçük, ayrı bir eğitim tablosunda gösterir."""

import argparse
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import partitioning


TABLE_NAME = "local.flight.snapshot_demo_positions"
SOURCE_TABLE = "local.flight.bronze_positions"


def arguments():
    parser = argparse.ArgumentParser(
        description="Iceberg snapshot/time-travel eğitim tablosunu güvenle oluşturur."
    )
    parser.add_argument("--warehouse", required=True, help="Mevcut Iceberg warehouse klasörü")
    parser.add_argument(
        "--phase",
        required=True,
        choices=("initial", "append"),
        help="initial ilk snapshot'ı oluşturur; append ikinci snapshot'ı ekler.",
    )
    parser.add_argument("--initial-rows", type=int, default=3)
    parser.add_argument("--append-rows", type=int, default=2)
    return parser.parse_args()


def sample_rows(spark, excluded_event_ids, limit):
    """Bronze'dan deterministik, küçük ve çakışmayan bir örnek döndürür."""

    source = spark.table(SOURCE_TABLE).select(
        "event_id", "icao24", "callsign", "origin_country", "observed_at", "ingested_at"
    )
    if excluded_event_ids is not None:
        source = source.join(excluded_event_ids, "event_id", "left_anti")
    return source.orderBy("event_id").limit(limit)


def show_snapshots(spark):
    """Iceberg metadata tablosundan snapshot zincirini okunabilir biçimde yazdırır."""

    snapshots = spark.sql(
        "SELECT snapshot_id, parent_id, committed_at, operation, summary "
        f"FROM {TABLE_NAME}.snapshots ORDER BY committed_at"
    ).collect()
    print("Snapshot geçmişi:")
    for row in snapshots:
        summary = row["summary"] or {}
        print(
            f"- id={row['snapshot_id']}; parent={row['parent_id']}; "
            f"işlem={row['operation']}; eklenen={summary.get('added-records', '0')}; "
            f"toplam={summary.get('total-records', '?')}; zaman={row['committed_at']}"
        )
    return snapshots


def main():
    args = arguments()
    if args.initial_rows <= 0 or args.append_rows <= 0:
        raise ValueError("Örnek satır sayıları pozitif olmalıdır.")

    warehouse = Path(args.warehouse)
    if not warehouse.is_dir():
        raise ValueError(f"Warehouse bulunamadı: {warehouse}")

    spark = (
        SparkSession.builder.appName("flight-iceberg-snapshot-demo")
        .config("spark.sql.session.timeZone", "UTC")
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", str(warehouse))
        .config("spark.sql.defaultCatalog", "local")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    try:
        table_exists = spark.catalog.tableExists(TABLE_NAME)
        if args.phase == "initial":
            if table_exists:
                raise ValueError(
                    f"{TABLE_NAME} zaten var; ilk snapshot korunuyor. "
                    "İkinci yazım için append kullanın."
                )
            initial = sample_rows(spark, None, args.initial_rows)
            if initial.count() != args.initial_rows:
                raise ValueError("Bronze kaynakta yeterli örnek satır yok.")
            initial.writeTo(TABLE_NAME).using("iceberg").partitionedBy(
                partitioning.days("observed_at")
            ).create()
            print(f"İlk snapshot oluşturuldu: {args.initial_rows} Bronze olayı.")
        else:
            if not table_exists:
                raise ValueError(
                    f"{TABLE_NAME} bulunamadı; önce initial aşamasını çalıştırın."
                )
            existing_ids = spark.table(TABLE_NAME).select("event_id")
            additional = sample_rows(spark, existing_ids, args.append_rows)
            if additional.count() != args.append_rows:
                raise ValueError("Bronze kaynakta eklenecek yeterli yeni örnek satır yok.")
            additional.writeTo(TABLE_NAME).append()
            print(f"İkinci snapshot'a {args.append_rows} yeni Bronze olayı eklendi.")

        snapshots = show_snapshots(spark)
        current_count = spark.table(TABLE_NAME).count()
        print(f"Güncel tablo sayısı: {current_count}")
        if len(snapshots) >= 2:
            first_snapshot_id = snapshots[0]["snapshot_id"]
            old_count = spark.sql(
                f"SELECT COUNT(*) AS event_count FROM {TABLE_NAME} "
                f"VERSION AS OF {first_snapshot_id}"
            ).first()["event_count"]
            print(
                f"Time-travel ({first_snapshot_id}) sayısı: {old_count}; "
                f"güncel tablodan fark: {current_count - old_count}"
            )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
