import json
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.build_daily_excerpt as build_daily_excerpt
from scripts.excerpt_pipeline.models import make_excerpt
from scripts.excerpt_pipeline.publishers import LocalJsonPublisher


def test_build_daily_excerpt_dry_run_outputs_excerpt_and_log(tmp_path):
    output_dir = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_daily_excerpt.py",
            "--dry-run",
            "--date",
            "2026-06-28",
            "--output-dir",
            str(output_dir),
            "--material-pool",
            "data/material_pool/seed.json",
            "--raw-note-html",
            "data/raw/xiaohongshu-c80cf3e1ef14.html",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "published excerpt" in result.stdout
    excerpt = json.loads((output_dir / "excerpts.json").read_text(encoding="utf-8"))[0]
    log = json.loads((output_dir / "job_logs.json").read_text(encoding="utf-8"))[0]
    assert excerpt["date"] == "2026-06-28"
    assert excerpt["title"]
    assert excerpt["paragraphs"]
    assert excerpt["image_urls"]
    assert log["status"] in {"success", "fallback_used"}


def test_build_from_note_url_uses_fetch_html(monkeypatch):
    html_text = Path("data/raw/xiaohongshu-c80cf3e1ef14.html").read_text(encoding="utf-8")
    calls = []

    def fake_fetch_html(url, timeout):
        calls.append((url, timeout))
        return html_text, 200

    monkeypatch.setattr(build_daily_excerpt, "fetch_html", fake_fetch_html)

    excerpt, skip_reason = build_daily_excerpt._build_from_note_url(
        "2026-06-29",
        "https://www.xiaohongshu.com/explore/example",
        7,
    )

    assert calls == [("https://www.xiaohongshu.com/explore/example", 7)]
    assert skip_reason == ""
    assert excerpt["date"] == "2026-06-29"
    assert excerpt["source_url"] == "https://www.xiaohongshu.com/explore/example"
    assert excerpt["paragraphs"]
    assert excerpt["image_urls"]


def test_build_from_note_url_reports_parse_failure(monkeypatch):
    def fake_fetch_html(url, timeout):
        return "<html>登录后推荐更懂你的笔记</html>", 200

    monkeypatch.setattr(build_daily_excerpt, "fetch_html", fake_fetch_html)

    excerpt, skip_reason = build_daily_excerpt._build_from_note_url(
        "2026-06-29",
        "https://www.xiaohongshu.com/explore/blocked",
        7,
    )

    assert excerpt is None
    assert skip_reason.startswith("note url parse failed:")


def test_make_excerpt_normalizes_image_urls_for_https_pages():
    excerpt = make_excerpt(
        date="2026-06-29",
        title="每日文摘",
        paragraphs=["正文"],
        summary="摘要",
        source_name="来源",
        source_url="https://example.com/source",
        source_account_id="account",
        content_hash="hash",
        publish_type="fresh",
        image_urls=[
            "http://example.com/image.jpg",
            " https://example.com/ready.jpg ",
            "",
            123,
            None,
        ],
    )

    assert excerpt["image_urls"] == [
        "https://example.com/image.jpg",
        "https://example.com/ready.jpg",
    ]


def test_dry_run_writes_failed_log_for_malformed_existing_excerpts(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "excerpts.json").write_text("{not json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_daily_excerpt.py",
            "--dry-run",
            "--date",
            "2026-06-28",
            "--output-dir",
            str(output_dir),
            "--material-pool",
            "data/material_pool/seed.json",
            "--raw-note-html",
            "data/raw/xiaohongshu-c80cf3e1ef14.html",
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    log = json.loads((output_dir / "job_logs.json").read_text(encoding="utf-8"))[0]
    assert log["status"] == "failed"
    assert "invalid JSON" in log["error_detail"]
    assert str(output_dir / "excerpts.json") in log["error_detail"]


def test_dry_run_fallback_log_includes_raw_note_skip_reason(tmp_path):
    output_dir = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_daily_excerpt.py",
            "--dry-run",
            "--date",
            "2026-06-28",
            "--output-dir",
            str(output_dir),
            "--material-pool",
            "data/material_pool/seed.json",
            "--raw-note-html",
            str(tmp_path / "missing.html"),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "published excerpt" in result.stdout
    log = json.loads((output_dir / "job_logs.json").read_text(encoding="utf-8"))[0]
    assert log["status"] == "fallback_used"
    assert log["message"] == "used fallback material: raw note html missing"


def test_local_json_publisher_validates_existing_json_and_does_not_mutate_item(tmp_path):
    publisher = LocalJsonPublisher(tmp_path)
    excerpt = {"title": "每日文摘"}

    item_id = publisher.publish_excerpt(excerpt)

    assert item_id == "local-1"
    assert "_id" not in excerpt
    saved = json.loads((tmp_path / "excerpts.json").read_text(encoding="utf-8"))
    assert saved[0]["_id"] == "local-1"

    (tmp_path / "job_logs.json").write_text('{"not": "a list"}', encoding="utf-8")
    with pytest.raises(ValueError, match="job_logs.json.*list"):
        publisher.publish_job_log({"status": "success"})


def test_github_actions_workflow_uses_note_url_secret_and_beijing_date():
    workflow = Path(".github/workflows/daily-excerpt.yml").read_text(encoding="utf-8")

    assert "XHS_NOTE_URL" in workflow
    assert "TZ=Asia/Shanghai date +%F" in workflow
    assert "python -m pytest -v" in workflow
    assert "--note-url" in workflow
    assert "--raw-note-html data/raw/xiaohongshu-c80cf3e1ef14.html" in workflow
