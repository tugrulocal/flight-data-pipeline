"""Bronze'da henüz sınıflandırılmamış olayların Silver dry-run analizini yapar."""

import argparse
from pathlib import Path

from pyspark.sql import SparkSession, functions as F

from hourly_traffic_report import add_quality_columns


def arguments():
    parser = argparse.ArgumentParser(
        description="Yeni Bronze olaylarının Silver kalite sonucunu yazmadan gösterir."
    )
    parser.add_argument("--warehouse", required=True, help="Mevcut Iceberg warehouse klasörü")
    parser.add_argument("--namespace", default="flight")
    parser.add_argument("--max-velocity-mps", type=float, default=400.0)
    parser.add_argument("--max-observation-lag-minutes", type=int, default=20)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Dry-run planını Silver ve Rejected tablolarına ekler.",
    )
    return parser.parse_args()


def main():
    args = arguments()
    warehouse = Path(args.warehouse)
    if not warehouse.is_dir():
        raise ValueError(f"Warehouse bulunamadı: {warehouse}")

    spark = (
        SparkSession.builder.appName("flight-iceberg-silver-refresh-dry-run")
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

    assessed = None
    try:
        prefix = f"local.{args.namespace}"
        bronze = spark.table(f"{prefix}.bronze_positions")
        silver_table = f"{prefix}.silver_positions"
        rejected_table = f"{prefix}.silver_rejected_positions"
        silver_ids = spark.table(silver_table).select("event_id")
        rejected_ids = spark.table(rejected_table).select("event_id")

        overlap = silver_ids.join(rejected_ids, "event_id", "inner").count()
        if overlap:
            raise ValueError(
                f"{overlap} event_id hem Silver hem Rejected içinde; sınıflandırma güvenli değil."
            )

        classified_ids = silver_ids.unionByName(rejected_ids)
        unclassified = bronze.join(classified_ids, "event_id", "left_anti")
        bronze_count = bronze.count()
        classified_count = classified_ids.count()
        unclassified_count = unclassified.count()
        assessed = add_quality_columns(
            unclassified,
            args.max_velocity_mps,
            args.max_observation_lag_minutes,
        ).cache()
        quality_rows = (
            assessed.groupBy("quality_status", "quality_reason")
            .count()
            .orderBy("quality_status", F.desc("count"), "quality_reason")
            .collect()
        )

        print("Silver yenileme dry-run sonucu (hiçbir tabloya yazılmadı):")
        print(f"- Bronze toplam: {bronze_count}")
        print(f"- Daha önce sınıflandırılmış: {classified_count}")
        print(f"- Silver'a henüz alınmamış yeni Bronze: {unclassified_count}")
        print("- Yeni batch kalite sonucu:")
        for row in quality_rows:
            reason = row["quality_reason"] or "kural ihlali yok"
            print(f"  - {row['quality_status']} | {reason}: {row['count']}")
        if not args.apply:
            print(
                "Bu sonuç, bir sonraki derste Silver ve Rejected tablolarına eklenecek "
                "kayıtların planıdır; bu komut yalnız okuma yaptı."
            )
            return

        accepted = assessed.where(F.col("quality_status") == "accepted")
        rejected = assessed.where(F.col("quality_status") == "rejected")
        accepted_count = accepted.count()
        rejected_count = rejected.count()
        # Iceberg her tablo için atomik snapshot commit'i verir. İki hedef tablo
        # olduğundan bir commit başarılı, diğeri başarısız kalabilir; yeniden
        # çalıştırmadaki anti-join yalnız henüz sınıflandırılmamış olayları ekler.
        if accepted_count:
            accepted.writeTo(silver_table).append()
        if rejected_count:
            rejected.writeTo(rejected_table).append()

        print(f"Silver'a eklenen kabul: {accepted_count}")
        print(f"Rejected'a eklenen red: {rejected_count}")
        print(f"Silver güncel satır sayısı: {spark.table(silver_table).count()}")
        print(f"Rejected güncel satır sayısı: {spark.table(rejected_table).count()}")
        print(
            "Gold tabloları henüz yenilenmedi; sonraki ders Gold'u tüm güncel "
            "Silver/Rejected sonuçlarından yeniden hesaplayacak."
        )
    finally:
        if assessed is not None:
            assessed.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
