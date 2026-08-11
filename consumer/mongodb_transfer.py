import argparse
import gzip
import os
import sys
from datetime import UTC
from typing import BinaryIO

from bson import json_util
from bson.json_util import JSONMode, JSONOptions
from pymongo import MongoClient
from pymongo.errors import PyMongoError


FORMAT_NAME = "flight-data-pipeline-mongodb-export"
FORMAT_VERSION = 1
COLLECTIONS = ("raw_positions", "live_positions")
BATCH_SIZE = 1_000
JSON_OPTIONS = JSONOptions(json_mode=JSONMode.CANONICAL, tz_aware=True, tzinfo=UTC)


def mongo_database():
    client = MongoClient(
        os.getenv("MONGODB_URI", "mongodb://mongodb:27017"),
        serverSelectionTimeoutMS=10_000,
    )
    database_name = os.getenv("MONGODB_DATABASE", "flightdb")
    client.admin.command("ping")
    return client, client[database_name]


def application_document_count(database) -> int:
    return sum(database[name].count_documents({}) for name in COLLECTIONS)


def write_json_line(stream: BinaryIO, value: object) -> None:
    stream.write(json_util.dumps(value, json_options=JSON_OPTIONS).encode())
    stream.write(b"\n")


def export_database(database, output: BinaryIO) -> None:
    with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as archive:
        write_json_line(
            archive,
            {
                "format": FORMAT_NAME,
                "format_version": FORMAT_VERSION,
                "database": database.name,
                "collections": list(COLLECTIONS),
            },
        )
        for collection_name in COLLECTIONS:
            for document in database[collection_name].find({}, batch_size=BATCH_SIZE):
                write_json_line(
                    archive,
                    {"collection": collection_name, "document": document},
                )


def insert_batch(database, collection_name: str, documents: list[dict]) -> None:
    if documents:
        database[collection_name].insert_many(documents, ordered=True)
        documents.clear()


def import_database(database, source: BinaryIO, replace: bool) -> None:
    with gzip.GzipFile(fileobj=source, mode="rb") as archive:
        header_line = archive.readline()
        if not header_line:
            raise ValueError("Yedek başlığı bulunamadı")
        header = json_util.loads(header_line, json_options=JSON_OPTIONS)
        if (
            header.get("format") != FORMAT_NAME
            or header.get("format_version") != FORMAT_VERSION
            or tuple(header.get("collections", ())) != COLLECTIONS
        ):
            raise ValueError("Desteklenmeyen veya bozuk yedek formatı")

        existing = application_document_count(database)
        if existing and not replace:
            raise ValueError(f"Hedef flightdb boş değil ({existing} belge)")
        if replace:
            for collection_name in COLLECTIONS:
                database[collection_name].drop()

        batches = {name: [] for name in COLLECTIONS}
        for line_number, line in enumerate(archive, start=2):
            try:
                record = json_util.loads(line, json_options=JSON_OPTIONS)
                collection_name = record["collection"]
                document = record["document"]
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Bozuk yedek kaydı, satır {line_number}") from exc
            if collection_name not in batches or not isinstance(document, dict):
                raise ValueError(f"Geçersiz collection/belge, satır {line_number}")
            batch = batches[collection_name]
            batch.append(document)
            if len(batch) >= BATCH_SIZE:
                insert_batch(database, collection_name, batch)

        for collection_name, batch in batches.items():
            insert_batch(database, collection_name, batch)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("export")
    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--replace", action="store_true")
    subparsers.add_parser("count")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    client = None
    try:
        client, database = mongo_database()
        if arguments.command == "export":
            export_database(database, sys.stdout.buffer)
        elif arguments.command == "import":
            import_database(database, sys.stdin.buffer, arguments.replace)
        else:
            print(application_document_count(database))
        return 0
    except (OSError, PyMongoError, ValueError) as exc:
        print(f"MongoDB transfer HATA: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
