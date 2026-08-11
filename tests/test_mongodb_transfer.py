import io
from datetime import UTC, datetime

import pytest
from bson import ObjectId

from consumer.mongodb_transfer import (
    application_document_count,
    export_database,
    import_database,
)


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def count_documents(self, _filter):
        return len(self.documents)

    def find(self, _filter, batch_size):
        assert batch_size > 0
        return iter(self.documents)

    def insert_many(self, documents, ordered):
        assert ordered is True
        self.documents.extend(documents)

    def drop(self):
        self.documents.clear()


class FakeDatabase:
    name = "flightdb"

    def __init__(self, raw=None, live=None):
        self.collections = {
            "raw_positions": FakeCollection(raw),
            "live_positions": FakeCollection(live),
        }

    def __getitem__(self, name):
        return self.collections[name]


def test_export_import_roundtrip_preserves_bson_types():
    object_id = ObjectId()
    observed_at = datetime(2026, 8, 11, 10, 30, tzinfo=UTC)
    source = FakeDatabase(
        raw=[{"_id": object_id, "observed_at": observed_at}],
        live=[{"_id": "4baa12", "on_ground": None}],
    )
    archive = io.BytesIO()

    export_database(source, archive)
    archive.seek(0)
    target = FakeDatabase()
    import_database(target, archive, replace=False)

    assert application_document_count(target) == 2
    restored = target["raw_positions"].documents[0]
    assert restored["_id"] == object_id
    assert restored["observed_at"] == observed_at
    assert target["live_positions"].documents[0]["on_ground"] is None


def test_import_refuses_nonempty_target_without_replace():
    archive = io.BytesIO()
    export_database(FakeDatabase(raw=[{"_id": "new"}]), archive)
    archive.seek(0)
    target = FakeDatabase(raw=[{"_id": "existing"}])

    with pytest.raises(ValueError, match="Hedef flightdb boş değil"):
        import_database(target, archive, replace=False)

    assert target["raw_positions"].documents == [{"_id": "existing"}]


def test_import_replace_drops_existing_application_collections():
    archive = io.BytesIO()
    export_database(FakeDatabase(raw=[{"_id": "new"}]), archive)
    archive.seek(0)
    target = FakeDatabase(
        raw=[{"_id": "existing"}],
        live=[{"_id": "existing-live"}],
    )

    import_database(target, archive, replace=True)

    assert target["raw_positions"].documents == [{"_id": "new"}]
    assert target["live_positions"].documents == []
