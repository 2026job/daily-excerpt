# Material Pool Replenishment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a half-hourly GitHub Actions replenishment path that processes at most one fresh Xiaohongshu post candidate per run.

**Architecture:** Add a small orchestration script that reuses existing Xiaohongshu profile and note extractors, existing cleaning helpers, and the existing JSON material pool. A separate `Material Replenishment` workflow runs every half hour and commits `data/material_pool/seed.json` or `data/material_pool/xiaohongshu_candidates.json` only when either changed.

**Tech Stack:** Python 3.11, pytest, GitHub Actions, existing urllib-based Xiaohongshu extractors.

---

## File Map

- Create `scripts/replenish_material_pool.py`: CLI and pure functions for selecting new posts, fetching note details when URLs exist, converting notes into candidate materials, storing metadata candidates when URLs are missing, appending to JSON pools, and writing job logs.
- Modify `scripts/excerpt_pipeline/material_pool.py`: add `save_material_pool`, `material_identity_keys`, and `append_unique_materials` helpers while preserving existing fallback behavior.
- Create `tests/test_replenish_material_pool.py`: TDD coverage for one-per-run replenishment, duplicate skipping, and failed detail handling.
- Create `.github/workflows/material-replenishment.yml`: run on half-hour cadence, grant `contents: write`, run replenisher, upload logs, and commit pool changes.
- Keep `.github/workflows/daily-excerpt.yml`: daily publish/deploy workflow remains on the daily schedule.
- Modify `README.md`: document the replenishment schedule and generated candidate behavior.

## Task 1: Material Pool Append Helpers

**Files:**
- Modify: `scripts/excerpt_pipeline/material_pool.py`
- Modify: `tests/test_material_pool.py`

- [ ] Step 1: Add failing tests in `tests/test_material_pool.py` for saving and unique append.

Add imports and tests:

```python
from scripts.excerpt_pipeline.material_pool import (
    append_unique_materials,
    load_material_pool,
    save_material_pool,
    select_fallback_material,
)


def test_save_material_pool_writes_pretty_json(tmp_path):
    path = tmp_path / "pool.json"

    save_material_pool(path, [{"id": "a", "title": "标题"}])

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == [{"id": "a", "title": "标题"}]
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_append_unique_materials_skips_existing_note_url_and_hash():
    existing = [
        _material("old", "hash-a", source_url="https://example.com/a"),
    ]
    incoming = [
        _material("same-url", "hash-b", source_url="https://example.com/a"),
        _material("same-hash", "hash-a", source_url="https://example.com/b"),
        _material("fresh", "hash-c", source_url="https://example.com/c"),
    ]

    combined, added = append_unique_materials(existing, incoming)

    assert [item["id"] for item in combined] == ["old", "fresh"]
    assert [item["id"] for item in added] == ["fresh"]
```

Also update `_material` helper to accept `source_url`:

```python
def _material(
    material_id,
    content_hash,
    *,
    status="candidate",
    title="标题",
    paragraphs=None,
    summary="摘要",
    source_url="",
):
    return {
        "id": material_id,
        "status": status,
        "content_hash": content_hash,
        "title": title,
        "paragraphs": paragraphs if paragraphs is not None else ["正文"],
        "summary": summary,
        "source_url": source_url,
    }
```

- [ ] Step 2: Run failing tests.

Run:

```bash
.venv/bin/python -m pytest tests/test_material_pool.py::test_save_material_pool_writes_pretty_json tests/test_material_pool.py::test_append_unique_materials_skips_existing_note_url_and_hash -v
```

Expected: fail because helpers are not defined.

- [ ] Step 3: Implement helpers in `scripts/excerpt_pipeline/material_pool.py`.

Add:

```python
def save_material_pool(path: Path, materials: List[Material]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(materials, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def material_identity_keys(material: Material) -> Set[str]:
    keys = set()
    for field in ("id", "content_hash", "source_url", "note_id"):
        value = material.get(field)
        if isinstance(value, str) and value.strip():
            keys.add(f"{field}:{value.strip()}")
    return keys


def append_unique_materials(
    existing: List[Material],
    incoming: Iterable[Material],
) -> tuple[List[Material], List[Material]]:
    combined = list(existing)
    seen = set()
    for material in combined:
        seen.update(material_identity_keys(material))

    added = []
    for material in incoming:
        keys = material_identity_keys(material)
        if keys & seen:
            continue
        combined.append(material)
        added.append(material)
        seen.update(keys)
    return combined, added
```

- [ ] Step 4: Run material pool tests.

Run:

```bash
.venv/bin/python -m pytest tests/test_material_pool.py -v
```

Expected: all tests pass.

## Task 2: Replenishment Script Core

**Files:**
- Create: `scripts/replenish_material_pool.py`
- Create: `tests/test_replenish_material_pool.py`

- [ ] Step 1: Write failing tests for replenishment.

Create `tests/test_replenish_material_pool.py` with tests that monkeypatch network calls:

```python
import json
from pathlib import Path

import scripts.replenish_material_pool as replenish


def _post(note_id="note-a", url="https://www.xiaohongshu.com/explore/note-a"):
    return {"note_id": note_id, "title": "候选标题", "url": url, "cover_url": "https://example.com/cover.jpg"}


def _note(title="详情标题", content="第一段。\n第二段。", url="https://www.xiaohongshu.com/explore/note-a"):
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

    monkeypatch.setattr(replenish, "load_profile_posts", lambda *args, **kwargs: {"posts": [_post(), _post("note-b", "https://www.xiaohongshu.com/explore/note-b")], "parse_status": "ok"})
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
    pool_path.write_text(json.dumps([{"id": "xiaohongshu-note-a", "status": "candidate", "content_hash": "old", "source_url": "https://www.xiaohongshu.com/explore/note-a", "title": "旧", "paragraphs": ["旧"], "summary": "旧"}], ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(replenish, "load_profile_posts", lambda *args, **kwargs: {"posts": [_post(), _post("note-b", "https://www.xiaohongshu.com/explore/note-b")], "parse_status": "ok"})
    monkeypatch.setattr(replenish, "fetch_html", lambda url, timeout: ("<html></html>", 200))
    monkeypatch.setattr(replenish, "extract_note", lambda html, url, account: _note(title="详情标题 B", url=url))

    added = replenish.replenish_material_pool(pool_path, output_dir, "profile", "欣欣的阅读疗愈记", 1, 7)

    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    assert added == 1
    assert len(pool) == 2
    assert pool[1]["source_url"] == "https://www.xiaohongshu.com/explore/note-b"


def test_replenish_logs_failed_detail_without_adding(tmp_path, monkeypatch):
    pool_path = tmp_path / "seed.json"
    output_dir = tmp_path / "output"
    pool_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(replenish, "load_profile_posts", lambda *args, **kwargs: {"posts": [_post()], "parse_status": "ok"})
    monkeypatch.setattr(replenish, "fetch_html", lambda url, timeout: ("<html></html>", 200))
    monkeypatch.setattr(replenish, "extract_note", lambda html, url, account: {"parse_status": "login_or_challenge", "note_url": url})

    added = replenish.replenish_material_pool(pool_path, output_dir, "profile", "欣欣的阅读疗愈记", 1, 7)

    assert added == 0
    assert json.loads(pool_path.read_text(encoding="utf-8")) == []
    log = json.loads((output_dir / "material_replenishment_logs.json").read_text(encoding="utf-8"))[0]
    assert log["status"] == "no_material_added"
    assert log["failed_candidates"][0]["reason"] == "detail parse failed: login_or_challenge"
```

- [ ] Step 2: Run failing tests.

Run:

```bash
.venv/bin/python -m pytest tests/test_replenish_material_pool.py -v
```

Expected: fail because `scripts/replenish_material_pool.py` does not exist.

- [ ] Step 3: Implement `scripts/replenish_material_pool.py`.

Implementation requirements:

- Use existing `fetch_xiaohongshu_user_posts.load_or_fetch_html` and `extract_profile_posts` in `load_profile_posts`.
- Use existing `fetch_xiaohongshu_note.fetch_html` and `extract_note` for detail pages.
- Convert a parsed note to material with fields: `id`, `status`, `title`, `paragraphs`, `summary`, `source_name`, `source_url`, `source_account_id`, `content_hash`, `image_urls`, `note_id`, `cover_url`, `created_at`.
- Use `rebuild_paragraphs(note["content"], "")` for paragraphs, `build_summary(paragraphs)` for summary, `content_hash(title, paragraphs)` for duplicate detection, `normalize_image_urls(note.get("image_urls", []))` for images, and `utc_now()` for `created_at`.
- Write logs to `output_dir / "material_replenishment_logs.json"` as a JSON list, appending new logs.
- Keep default `--max-details 1`.

- [ ] Step 4: Run replenishment tests.

Run:

```bash
.venv/bin/python -m pytest tests/test_replenish_material_pool.py -v
```

Expected: all tests pass.

## Task 3: Workflow Integration

**Files:**
- Modify: `.github/workflows/daily-excerpt.yml`
- Modify: `tests/test_build_daily_excerpt.py`

- [ ] Step 1: Add failing workflow assertions to `tests/test_build_daily_excerpt.py`.

Extend `test_github_actions_workflow_uses_note_url_secret_and_beijing_date` with:

```python
    assert 'cron: "7,37 * * * *"' in workflow
    assert "contents: write" in workflow
    assert "scripts/replenish_material_pool.py" in workflow
    assert "Commit replenished material pool" in workflow
```

- [ ] Step 2: Run the workflow test.

Run:

```bash
.venv/bin/python -m pytest tests/test_build_daily_excerpt.py::test_github_actions_workflow_uses_note_url_secret_and_beijing_date -v
```

Expected: fail because workflow has the old daily schedule and no replenishment step.

- [ ] Step 3: Update workflow.

Changes:

- Replace schedule with `cron: "7,37 * * * *"`.
- Change `permissions.contents` from `read` to `write`.
- Add a step after tests:

```yaml
      - name: Replenish material pool
        run: |
          python scripts/replenish_material_pool.py \
            --material-pool data/material_pool/seed.json \
            --output-dir data/output \
            --max-details 1
```

- Add commit step after replenishment:

```yaml
      - name: Commit replenished material pool
        run: |
          if ! git diff --quiet -- data/material_pool/seed.json data/output/material_replenishment_logs.json; then
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git add data/material_pool/seed.json data/output/material_replenishment_logs.json
            git commit -m "chore: replenish material pool"
            git push
          fi
```

- [ ] Step 4: Run workflow test.

Run:

```bash
.venv/bin/python -m pytest tests/test_build_daily_excerpt.py::test_github_actions_workflow_uses_note_url_secret_and_beijing_date -v
```

Expected: pass.

## Task 4: Docs and Full Verification

**Files:**
- Modify: `README.md`

- [ ] Step 1: Update README.

Add a section explaining:

- The workflow runs every half hour at minute 7 and 37.
- Each run attempts to add at most one fresh post detail to `data/material_pool/seed.json`.
- Action commits the updated pool back to GitHub only when the pool changed.
- The script does not bypass login, CAPTCHA, rate limits, or private content.

- [ ] Step 2: Run full tests.

Run:

```bash
.venv/bin/python -m pytest -v
```

Expected: all tests pass.

- [ ] Step 3: Run local fixture replenishment smoke test.

Run with monkeypatch-free defaults only if cache exists:

```bash
.venv/bin/python scripts/replenish_material_pool.py --material-pool /tmp/daily-excerpt-seed.json --output-dir /tmp/daily-excerpt-output --max-details 1 --profile-url https://www.xiaohongshu.com/user/profile/5c1db0ab0000000005013197
```

Expected: exits 0 or exits with a clear public-page parse/fetch failure. Do not commit `/tmp` outputs.

- [ ] Step 4: Commit and push.

```bash
git add scripts/replenish_material_pool.py scripts/excerpt_pipeline/material_pool.py tests/test_material_pool.py tests/test_replenish_material_pool.py tests/test_build_daily_excerpt.py .github/workflows/daily-excerpt.yml README.md docs/superpowers/specs/2026-06-29-material-pool-replenishment-design.md docs/superpowers/plans/2026-06-29-material-pool-replenishment.md
git commit -m "feat: replenish material pool from profile"
```

Push using normal git or GitHub API if HTTPS push hangs.
