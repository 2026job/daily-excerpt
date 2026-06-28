import json
import subprocess
from pathlib import Path

import pytest

from scripts.excerpt_pipeline.publishers import LocalJsonPublisher


def test_build_daily_excerpt_dry_run_outputs_excerpt_and_log(tmp_path):
    output_dir = tmp_path / "output"
    result = subprocess.run(
        [
            ".venv/bin/python",
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
    assert log["status"] in {"success", "fallback_used"}


def test_dry_run_writes_failed_log_for_malformed_existing_excerpts(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "excerpts.json").write_text("{not json", encoding="utf-8")

    result = subprocess.run(
        [
            ".venv/bin/python",
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
            ".venv/bin/python",
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
