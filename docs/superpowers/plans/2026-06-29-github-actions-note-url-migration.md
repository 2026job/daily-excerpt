# GitHub Actions Note URL Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GitHub Actions able to run the daily excerpt MVP against a configured public note URL, while retaining fixture fallback.

**Architecture:** Reuse the existing Python pipeline and add a `--note-url` input path beside `--raw-note-html`. The workflow reads `XHS_NOTE_URL` from GitHub secrets, passes an explicit Asia/Shanghai date, and falls back to fixture mode when the secret is empty.

**Tech Stack:** Python 3, pytest, GitHub Actions, existing Xiaohongshu extractor modules.

---

## Task 1: Pipeline `--note-url` Support

**Files:**
- Modify: `scripts/build_daily_excerpt.py`
- Modify: `tests/test_build_daily_excerpt.py`

- [ ] **Step 1: Write failing tests**

Add tests that monkeypatch `scripts.build_daily_excerpt.fetch_html` to avoid live network and verify `--note-url` publishes a fresh excerpt. Add another test that missing `--note-url` fetch failure falls back and logs the reason.

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_build_daily_excerpt.py -v
```

Expected: fails because `--note-url` is not recognized or `fetch_html` is not imported.

- [ ] **Step 3: Implement**

In `scripts/build_daily_excerpt.py`:

- Import `fetch_html` from `fetch_xiaohongshu_note`.
- Add `--note-url` and `--timeout`.
- Prefer `--note-url` over `--raw-note-html`.
- Add `_build_from_note_url(date, note_url, timeout)` that calls `fetch_html`, `extract_note`, then shared excerpt-building logic.
- Keep `--raw-note-html` fixture path working.
- Preserve fallback behavior and job logs.

- [ ] **Step 4: Run GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_build_daily_excerpt.py -v
```

Expected: all build daily excerpt tests pass.

---

## Task 2: Workflow Secret and Beijing Date

**Files:**
- Modify: `.github/workflows/daily-excerpt.yml`
- Modify: `tests/test_build_daily_excerpt.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing workflow text test**

Add a test that reads `.github/workflows/daily-excerpt.yml` and asserts it contains:

- `XHS_NOTE_URL`
- `TZ=Asia/Shanghai date +%F`
- `--note-url`
- fixture fallback to `--raw-note-html`

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_build_daily_excerpt.py -v
```

Expected: fails because workflow does not include note URL mode.

- [ ] **Step 3: Implement workflow and docs**

Update workflow run step:

```bash
RUN_DATE="$(TZ=Asia/Shanghai date +%F)"
if [ -n "${XHS_NOTE_URL}" ]; then
  python scripts/build_daily_excerpt.py --dry-run --date "$RUN_DATE" --note-url "$XHS_NOTE_URL"
else
  python scripts/build_daily_excerpt.py --dry-run --date "$RUN_DATE" --raw-note-html data/raw/xiaohongshu-c80cf3e1ef14.html
fi
```

Add `XHS_NOTE_URL` to env from secrets and document it in `README.md`.

- [ ] **Step 4: Run verification**

Run:

```bash
.venv/bin/python -m pytest -v
python3 -m json.tool miniprogram/app.json >/dev/null
python3 -m json.tool miniprogram/project.config.json >/dev/null
```

Expected: all tests pass and JSON files validate.

---

## Self-Review

Spec coverage:

- `--note-url`: Task 1.
- GitHub Secret `XHS_NOTE_URL`: Task 2.
- Beijing date: Task 2.
- Fixture fallback: Task 2.
- Artifact output remains unchanged: existing workflow upload remains.

Placeholder scan:

- No placeholders or deferred implementation notes.

Type consistency:

- Existing excerpt dict fields remain unchanged.
