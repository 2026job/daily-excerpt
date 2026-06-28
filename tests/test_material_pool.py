import json

import pytest

from scripts.excerpt_pipeline.material_pool import load_material_pool, select_fallback_material


def _material(
    material_id,
    content_hash,
    *,
    status="candidate",
    title="标题",
    paragraphs=None,
    summary="摘要",
):
    return {
        "id": material_id,
        "status": status,
        "content_hash": content_hash,
        "title": title,
        "paragraphs": paragraphs if paragraphs is not None else ["正文"],
        "summary": summary,
    }


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
        _material("used", "a", status="used"),
        _material("duplicate", "b"),
        _material("fresh", "c"),
    ]
    selected = select_fallback_material(pool, published_hashes={"b"})
    assert selected["id"] == "fresh"


def test_select_fallback_material_skips_duplicate_hash_seen_earlier_in_pool():
    pool = [
        _material("used", "x", status="used"),
        _material("duplicate", "x"),
        _material("fresh", "y"),
    ]

    selected = select_fallback_material(pool)

    assert selected["id"] == "fresh"


def test_select_fallback_material_skips_missing_or_empty_content_hash():
    pool = [
        {"id": "missing", "status": "candidate"},
        {"id": "empty", "status": "candidate", "content_hash": ""},
        _material("fresh", "fresh-hash"),
    ]

    selected = select_fallback_material(pool)

    assert selected["id"] == "fresh"


def test_select_fallback_material_skips_non_string_content_hash():
    pool = [
        {"id": "list-hash", "status": "candidate", "content_hash": ["bad"]},
        {"id": "dict-hash", "status": "candidate", "content_hash": {"bad": True}},
        _material("fresh", "fresh-hash"),
    ]

    selected = select_fallback_material(pool)

    assert selected["id"] == "fresh"


def test_select_fallback_material_skips_malformed_candidates():
    pool = [
        {
            "id": "missing-title",
            "status": "candidate",
            "content_hash": "missing-title",
            "paragraphs": ["正文"],
            "summary": "摘要",
        },
        {
            "id": "empty-paragraphs",
            "status": "candidate",
            "content_hash": "empty-paragraphs",
            "title": "标题",
            "paragraphs": [],
            "summary": "摘要",
        },
        {
            "id": "missing-summary",
            "status": "candidate",
            "content_hash": "missing-summary",
            "title": "标题",
            "paragraphs": ["正文"],
        },
        {
            "id": "fresh",
            "status": "candidate",
            "content_hash": "fresh-hash",
            "title": "标题",
            "paragraphs": ["正文"],
            "summary": "摘要",
        },
    ]

    selected = select_fallback_material(pool)

    assert selected["id"] == "fresh"


def test_select_fallback_material_returns_none_when_empty():
    assert select_fallback_material([], published_hashes=set()) is None
