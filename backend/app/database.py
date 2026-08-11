from pymongo import DESCENDING, MongoClient

from .contracts import (
    PUBLIC_AIRCRAFT_PROJECTION,
    public_aircraft_from_event,
)


class MongoRepository:
    """REST endpoint'lerinin kullandığı MongoDB okuma katmanı."""

    def __init__(self, uri, database_name):
        self.client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            tz_aware=True,
        )
        database = self.client[database_name]
        self.live_positions = database["live_positions"]
        self.raw_positions = database["raw_positions"]

    def ping(self):
        """MongoDB bağlantısının cevap verdiğini doğrular."""

        self.client.admin.command("ping")

    def list_live_aircraft(self, limit, observed_since):
        """En yeni canlı uçak durumlarını döndürür."""

        cursor = (
            self.live_positions
            .find(
                {"observed_at": {"$gte": observed_since}},
                PUBLIC_AIRCRAFT_PROJECTION,
            )
            .sort("observed_at", DESCENDING)
            .limit(limit + 1)
        )

        items = [
            normalize_document(document)
            for document in cursor
        ]
        return items[:limit], len(items) > limit

    def get_live_aircraft(self, icao24):
        """Bir uçağın son bilinen durumunu döndürür."""

        document = self.live_positions.find_one(
            {"_id": icao24.lower()},
            PUBLIC_AIRCRAFT_PROJECTION,
        )

        return normalize_document(document)

    def get_aircraft_history(self, icao24, limit):
        """Bir uçağın geçmiş konumlarını en yeniden eskiye döndürür."""

        cursor = (
            self.raw_positions
            .find(
                {"icao24": icao24.lower()},
                PUBLIC_AIRCRAFT_PROJECTION,
            )
            .sort("observed_at", DESCENDING)
            .limit(limit)
        )

        return [
            normalize_document(document)
            for document in cursor
        ]

    def get_live_statistics(self, observed_since):
        """Canlı uçak koleksiyonundan temel sayaçları hesaplar."""

        rows = list(
            self.live_positions.aggregate(
                [
                    {"$match": {"observed_at": {"$gte": observed_since}}},
                    {
                        "$group": {
                            "_id": None,
                            "total_aircraft": {"$sum": 1},
                            "airborne": {
                                "$sum": {
                                    "$cond": [
                                        {"$eq": ["$on_ground", False]}, 1, 0
                                    ]
                                }
                            },
                            "on_ground": {
                                "$sum": {
                                    "$cond": [
                                        {"$eq": ["$on_ground", True]}, 1, 0
                                    ]
                                }
                            },
                            "unknown_ground_state": {
                                "$sum": {
                                    "$cond": [
                                        {
                                            "$in": [
                                                {"$type": "$on_ground"},
                                                ["bool"],
                                            ]
                                        },
                                        0,
                                        1,
                                    ]
                                }
                            },
                            "last_observed_at": {"$max": "$observed_at"},
                        }
                    },
                    {"$project": {"_id": 0}},
                ]
            )
        )

        if rows:
            return rows[0]

        return {
            "total_aircraft": 0,
            "airborne": 0,
            "on_ground": 0,
            "unknown_ground_state": 0,
            "last_observed_at": None,
        }

    def get_latest_ingested_at(self):
        latest = self.live_positions.find_one(
            {},
            sort=[("ingested_at", DESCENDING)],
            projection={"ingested_at": 1},
        )
        return latest.get("ingested_at") if latest else None

    def close(self):
        """MongoDB bağlantı havuzunu kapatır."""

        self.client.close()


def normalize_document(document):
    """MongoDB belgesini JSON'a uygun bir sözlüğe dönüştürür."""

    if document is None:
        return None

    return public_aircraft_from_event(document)
