import json
import subprocess
from pathlib import Path


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
