import json

import scripts.replenish_material_pool as replenish


def _post(note_id="note-a", url="https://www.xiaohongshu.com/explore/note-a"):
    return {
        "note_id": note_id,
        "title": "候选标题",
        "url": url,
        "cover_url": "https://example.com/cover.jpg",
    }


def _note(
    title="详情标题",
    content="第一段。\n第二段。",
    url="https://www.xiaohongshu.com/explore/note-a",
):
    return {
        "parse_status": "ok",
        "title": title,
        "content": content,
        "note_url": url,
        "account_name": "欣欣的阅读疗愈记",
        "image_urls": ["http://example.com/image.jpg"],
    }


def test_replenish_adds_one_new_material(tmp_path, monkeypatch):
    pool_path = tmp_path / "seed.json"
    output_dir = tmp_path / "output"
    pool_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        replenish,
        "load_profile_posts",
        lambda *args, **kwargs: {
            "posts": [
                _post(),
                _post("note-b", "https://www.xiaohongshu.com/explore/note-b"),
            ],
            "parse_status": "ok",
        },
    )
    monkeypatch.setattr(replenish, "fetch_html", lambda url, timeout: ("<html></html>", 200))
    monkeypatch.setattr(replenish, "extract_note", lambda html, url, account: _note(url=url))

    added = replenish.replenish_material_pool(
        pool_path=pool_path,
        output_dir=output_dir,
        profile_url="https://www.xiaohongshu.com/user/profile/example",
        account="欣欣的阅读疗愈记",
        max_details=1,
        timeout=7,
    )

    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    assert added == 1
    assert len(pool) == 1
    assert pool[0]["status"] == "candidate"
    assert pool[0]["source_url"] == "https://www.xiaohongshu.com/explore/note-a"
    assert pool[0]["image_urls"] == ["https://example.com/image.jpg"]
    log = json.loads((output_dir / "material_replenishment_logs.json").read_text(encoding="utf-8"))[0]
    assert log["status"] == "success"
    assert log["added_count"] == 1


def test_replenish_skips_existing_and_adds_next(tmp_path, monkeypatch):
    pool_path = tmp_path / "seed.json"
    output_dir = tmp_path / "output"
    pool_path.write_text(
        json.dumps(
            [
                {
                    "id": "xiaohongshu-note-a",
                    "status": "candidate",
                    "content_hash": "old",
                    "source_url": "https://www.xiaohongshu.com/explore/note-a",
                    "title": "旧",
                    "paragraphs": ["旧"],
                    "summary": "旧",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        replenish,
        "load_profile_posts",
        lambda *args, **kwargs: {
            "posts": [
                _post(),
                _post("note-b", "https://www.xiaohongshu.com/explore/note-b"),
            ],
            "parse_status": "ok",
        },
    )
    monkeypatch.setattr(replenish, "fetch_html", lambda url, timeout: ("<html></html>", 200))
    monkeypatch.setattr(
        replenish,
        "extract_note",
        lambda html, url, account: _note(title="详情标题 B", url=url),
    )

    added = replenish.replenish_material_pool(
        pool_path,
        output_dir,
        "profile",
        "欣欣的阅读疗愈记",
        1,
        7,
    )

    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    assert added == 1
    assert len(pool) == 2
    assert pool[1]["source_url"] == "https://www.xiaohongshu.com/explore/note-b"


def test_replenish_logs_failed_detail_without_adding(tmp_path, monkeypatch):
    pool_path = tmp_path / "seed.json"
    output_dir = tmp_path / "output"
    pool_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        replenish,
        "load_profile_posts",
        lambda *args, **kwargs: {"posts": [_post()], "parse_status": "ok"},
    )
    monkeypatch.setattr(replenish, "fetch_html", lambda url, timeout: ("<html></html>", 200))
    monkeypatch.setattr(
        replenish,
        "extract_note",
        lambda html, url, account: {"parse_status": "login_or_challenge", "note_url": url},
    )

    added = replenish.replenish_material_pool(
        pool_path,
        output_dir,
        "profile",
        "欣欣的阅读疗愈记",
        1,
        7,
    )

    assert added == 0
    assert json.loads(pool_path.read_text(encoding="utf-8")) == []
    log = json.loads((output_dir / "material_replenishment_logs.json").read_text(encoding="utf-8"))[0]
    assert log["status"] == "no_material_added"
    assert log["failed_candidates"][0]["reason"] == "detail parse failed: login_or_challenge"


def test_replenish_stores_metadata_candidate_when_detail_url_is_missing(tmp_path, monkeypatch):
    pool_path = tmp_path / "seed.json"
    candidate_pool_path = tmp_path / "xiaohongshu_candidates.json"
    output_dir = tmp_path / "output"
    pool_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        replenish,
        "load_profile_posts",
        lambda *args, **kwargs: {
            "posts": [
                _post(note_id="", url=""),
                _post(note_id="", url=""),
            ],
            "parse_status": "ok",
        },
    )

    added = replenish.replenish_material_pool(
        pool_path=pool_path,
        output_dir=output_dir,
        profile_url="profile",
        account="欣欣的阅读疗愈记",
        max_details=1,
        timeout=7,
        candidate_pool_path=candidate_pool_path,
    )

    assert added == 0
    assert json.loads(pool_path.read_text(encoding="utf-8")) == []
    candidates = json.loads(candidate_pool_path.read_text(encoding="utf-8"))
    assert len(candidates) == 1
    assert candidates[0]["status"] == "candidate_metadata"
    assert candidates[0]["title"] == "候选标题"
    assert candidates[0]["cover_url"] == "https://example.com/cover.jpg"
    log = json.loads((output_dir / "material_replenishment_logs.json").read_text(encoding="utf-8"))[0]
    assert log["candidate_added_count"] == 1


def test_replenish_attempts_at_most_max_details_candidates(tmp_path, monkeypatch):
    pool_path = tmp_path / "seed.json"
    output_dir = tmp_path / "output"
    pool_path.write_text("[]", encoding="utf-8")
    fetched_urls = []

    monkeypatch.setattr(
        replenish,
        "load_profile_posts",
        lambda *args, **kwargs: {
            "posts": [
                _post(note_id="note-a", url="https://www.xiaohongshu.com/explore/note-a"),
                _post(note_id="note-b", url="https://www.xiaohongshu.com/explore/note-b"),
            ],
            "parse_status": "ok",
        },
    )
    monkeypatch.setattr(
        replenish,
        "fetch_html",
        lambda url, timeout: (fetched_urls.append(url) or ("<html></html>", 200)),
    )
    monkeypatch.setattr(
        replenish,
        "extract_note",
        lambda html, url, account: {"parse_status": "login_or_challenge", "note_url": url},
    )

    added = replenish.replenish_material_pool(
        pool_path=pool_path,
        output_dir=output_dir,
        profile_url="profile",
        account="欣欣的阅读疗愈记",
        max_details=1,
        timeout=7,
    )

    assert added == 0
    assert fetched_urls == ["https://www.xiaohongshu.com/explore/note-a"]
    log = json.loads((output_dir / "material_replenishment_logs.json").read_text(encoding="utf-8"))[0]
    assert log["attempted_count"] == 1
    assert len(log["failed_candidates"]) == 1
