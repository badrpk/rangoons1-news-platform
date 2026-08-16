from chrona import ChronaArchive


def test_deterministic_id_and_deduplication():
    archive = ChronaArchive()
    first = archive.add(timestamp="2026-01-01T10:00:00Z", title="A", source="wire")
    second = archive.add(timestamp="2026-01-01T10:00:00+00:00", title="A", source="wire")
    assert first.id == second.id
    assert archive.snapshot()["count"] == 1


def test_timeline_filters_by_range_tag_and_source():
    archive = ChronaArchive()
    archive.add(timestamp="2026-01-01T10:00:00Z", title="A", source="wire", tags=["energy"])
    archive.add(timestamp="2026-01-02T10:00:00Z", title="B", source="local", tags=["mobility"])
    archive.add(timestamp="2026-01-03T10:00:00Z", title="C", source="wire", tags=["energy", "policy"])

    assert [e.title for e in archive.timeline(tag="energy")] == ["A", "C"]
    assert [e.title for e in archive.timeline(source="wire")] == ["A", "C"]
    assert [e.title for e in archive.timeline(start="2026-01-02T00:00:00Z")] == ["B", "C"]


def test_search_matches_body_tags_and_source():
    archive = ChronaArchive()
    archive.add(timestamp="2026-01-01T10:00:00Z", title="Grid update", source="wire", body="Solar capacity expanded", tags=["energy"])
    assert archive.search("solar")[0].title == "Grid update"
    assert archive.search("energy")[0].title == "Grid update"
    assert archive.search("wire")[0].title == "Grid update"


def test_snapshot_hash_is_stable_across_insertion_order():
    a = ChronaArchive()
    b = ChronaArchive()
    events = [
        dict(timestamp="2026-01-02T00:00:00Z", title="B", source="s"),
        dict(timestamp="2026-01-01T00:00:00Z", title="A", source="s"),
    ]
    for item in events:
        a.add(**item)
    for item in reversed(events):
        b.add(**item)
    assert a.snapshot()["sha256"] == b.snapshot()["sha256"]


def test_save_load_round_trip(tmp_path):
    archive = ChronaArchive()
    archive.add(timestamp="2026-01-01T00:00:00Z", title="A", source="s", tags=["x"])
    file = tmp_path / "archive.json"
    archive.save(file)
    restored = ChronaArchive.load(file)
    assert restored.snapshot() == archive.snapshot()
