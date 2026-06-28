import json

import pytest

from scripts.excerpt_pipeline.material_pool import load_material_pool, select_fallback_material


def test_load_material_pool_reads_list(tmp_path):
    path = tmp_path / "pool.json"
    path.write_text(json.dumps([{"id": "a", "status": "candidate"}]), encoding="utf-8")
    assert load_material_pool(path) == [{"id": "a", "status": "candidate"}]


def test_load_material_pool_missing_file_returns_empty_list(tmp_path):
    assert load_material_pool(tmp_path / "missing.json") == []


def test_load_material_pool_rejects_non_list_json(tmp_path):
    path = tmp_path / "pool.json"
    path.write_text(json.dumps({"id": "a"}), encoding="utf-8")

    with pytest.raises(ValueError, match="material pool must be a list"):
        load_material_pool(path)


def test_select_fallback_material_skips_used_and_duplicate_hash():
    pool = [
        {"id": "used", "status": "used", "content_hash": "a"},
        {"id": "duplicate", "status": "candidate", "content_hash": "b"},
        {"id": "fresh", "status": "candidate", "content_hash": "c"},
    ]
    selected = select_fallback_material(pool, published_hashes={"b"})
    assert selected["id"] == "fresh"


def test_select_fallback_material_skips_duplicate_hash_seen_earlier_in_pool():
    pool = [
        {"id": "used", "status": "used", "content_hash": "x"},
        {"id": "duplicate", "status": "candidate", "content_hash": "x"},
        {"id": "fresh", "status": "candidate", "content_hash": "y"},
    ]

    selected = select_fallback_material(pool)

    assert selected["id"] == "fresh"


def test_select_fallback_material_skips_missing_or_empty_content_hash():
    pool = [
        {"id": "missing", "status": "candidate"},
        {"id": "empty", "status": "candidate", "content_hash": ""},
        {"id": "fresh", "status": "candidate", "content_hash": "fresh-hash"},
    ]

    selected = select_fallback_material(pool)

    assert selected["id"] == "fresh"


def test_select_fallback_material_returns_none_when_empty():
    assert select_fallback_material([], published_hashes=set()) is None
