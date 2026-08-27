"""Bir Mongo batch export'unun Iceberg Bronze'a etkisini yazmadan ölçer."""

import argparse
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

from hourly_traffic_report import raw_positions_dataframe


def arguments():
    parser = argparse.ArgumentParser(
        description="Batch export ile Iceberg Bronze arasındaki yeni event_id'leri ölçer."
    )
    parser.add_argument("--input", required=True, help="Yeni Mongo Extended JSONL(.gz) export'u")
    parser.add_argument("--warehouse", required=True, help="Mevcut Iceberg warehouse klasörü")
    parser.add_argument("--namespace", default="flight")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Yalnız ölçer, Iceberg'e yazmaz.",
    )
    mode.add_argument(
        "--apply-bronze",
        action="store_true",
        help="Yalnız doğrulanmış yeni olayları Bronze'a ekler.",
    )
    return parser.parse_args()


def main():
    args = arguments()

    warehouse = Path(args.warehouse)
    if not warehouse.is_dir():
        raise ValueError(f"Warehouse bulunamadı: {warehouse}")

    bronze_table = f"local.{args.namespace}.bronze_positions"
    spark = (
        SparkSession.builder.appName("flight-iceberg-batch-refresh-dry-run")
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
        incoming_raw = raw_positions_dataframe(spark, args.input)
        incoming = incoming_raw.select("event_id")
        bronze_ids = spark.table(bronze_table).select("event_id")

        incoming_count = incoming.count()
        incoming_distinct_count = incoming.distinct().count()
        existing_count = bronze_ids.count()
        unseen_ids = incoming.join(bronze_ids, "event_id", "left_anti")
        unseen_count = unseen_ids.count()

        print("Batch yenileme karşılaştırması:")
        print(f"- Yeni Mongo export'u: {incoming_count} satır")
        print(f"- Export benzersiz event_id: {incoming_distinct_count}")
        print(f"- Mevcut Iceberg Bronze: {existing_count} satır")
        print(f"- Iceberg'de olmayan yeni event_id: {unseen_count}")
        if incoming_count != incoming_distinct_count:
            raise ValueError(
                "Export içinde tekrar eden event_id var; Bronze'a hiçbir kayıt eklenmedi."
            )

        if args.dry_run:
            print("Dry-run tamamlandı: hiçbir Iceberg tablosuna yazılmadı.")
            return

        if unseen_count == 0:
            print("Yeni event_id yok; Bronze değişmedi ve yeni snapshot oluşmadı.")
            return

        new_bronze = (
            incoming_raw.join(unseen_ids, "event_id", "left_semi")
            .withColumn("observed_date", F.to_date("observed_at"))
        )
        # Iceberg append tek bir atomik commit üretir. Commit başarılı olmazsa
        # yeni snapshot görünmez; mevcut Bronze korunur.
        new_bronze.writeTo(bronze_table).append()
        current_count = spark.table(bronze_table).count()
        latest = spark.sql(
            f"SELECT snapshot_id, parent_id, committed_at, summary "
            f"FROM {bronze_table}.snapshots ORDER BY committed_at DESC LIMIT 1"
        ).first()
        print(f"Bronze'a eklenen yeni olay: {unseen_count}")
        print(f"Bronze güncel satır sayısı: {current_count}")
        print(
            f"Yeni Bronze snapshot: {latest['snapshot_id']}; "
            f"parent: {latest['parent_id']}; "
            f"eklenen: {(latest['summary'] or {}).get('added-records', '?')}"
        )
        print(
            "Bu ders yalnız Bronze'u yeniledi. Silver/Gold henüz eski snapshot'tadır; "
            "bir sonraki ders onları tutarlı biçimde yenileyecek."
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
