# Daily Excerpt Miniprogram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal WeChat Mini Program and automated publishing pipeline for daily short excerpts, with fixed public sources, OCR-assisted paragraph cleanup, fallback material, and history browsing.

**Architecture:** Keep the system split into a Python content pipeline and a WeChat Mini Program frontend. The pipeline can run locally or in GitHub Actions, writes local JSON during dry runs, and later publishes to WeChat Cloud Database through a dedicated publisher module. The Mini Program reads published excerpts from cloud database and displays today, history, and detail views.

**Tech Stack:** Python 3 standard library plus optional Tencent Cloud OCR SDK, pytest, GitHub Actions, WeChat Mini Program JavaScript/WXML/WXSS, WeChat Cloud Database.

---

## File Structure

Create and modify these files:

- Create `README.md`: project overview, local commands, environment variables, and workflow summary.
- Create `.gitignore`: ignore local OS files, Python caches, local secrets, generated caches, and Superpowers visual companion state.
- Create `requirements-dev.txt`: test-only Python dependencies.
- Create `requirements.txt`: runtime Python dependencies for GitHub Actions.
- Create `scripts/excerpt_pipeline/__init__.py`: package marker.
- Create `scripts/excerpt_pipeline/models.py`: typed dictionaries and lightweight validation helpers for excerpts, sources, material pool items, and job logs.
- Create `scripts/excerpt_pipeline/cleaning.py`: pure text normalization, sentence splitting, paragraph rebuilding, summary creation, and content hashing.
- Create `scripts/excerpt_pipeline/material_pool.py`: load, select, and mark fallback material from local JSON.
- Create `scripts/excerpt_pipeline/ocr.py`: OCR abstraction with a no-op fake implementation and Tencent Cloud implementation guarded by environment variables.
- Create `scripts/excerpt_pipeline/publishers.py`: local JSON publisher and WeChat Cloud Database publisher interface.
- Create `scripts/build_daily_excerpt.py`: CLI entrypoint that runs the daily update pipeline.
- Create `config/sources.json`: fixed source list, initially containing the tested Xiaohongshu account.
- Create `data/material_pool/seed.json`: local fallback material seed derived from existing extracted material.
- Create `.github/workflows/daily-excerpt.yml`: scheduled and manual pipeline run.
- Create `miniprogram/app.js`, `miniprogram/app.json`, `miniprogram/app.wxss`: Mini Program shell.
- Create `miniprogram/project.config.json`: WeChat DevTools project config with placeholder appid.
- Create `miniprogram/utils/excerpts.js`: cloud database read helpers.
- Create `miniprogram/pages/today/today.js`, `.wxml`, `.wxss`: today page.
- Create `miniprogram/pages/history/history.js`, `.wxml`, `.wxss`: history page.
- Create `miniprogram/pages/detail/detail.js`, `.wxml`, `.wxss`: detail page.
- Create `tests/fixtures/xiaohongshu-note.html`: stable fixture copied from existing raw HTML.
- Create `tests/test_cleaning.py`: unit tests for text cleanup and paragraph rebuilding.
- Create `tests/test_material_pool.py`: unit tests for fallback selection.
- Create `tests/test_build_daily_excerpt.py`: integration tests for dry-run pipeline.
- Modify `scripts/fetch_xiaohongshu_note.py`: expose reusable `extract_note` behavior without changing CLI.
- Modify `scripts/fetch_xiaohongshu_user_posts.py`: expose reusable profile parsing without changing CLI.

The first implementation pass should stop at a local dry-run pipeline and Mini Program source files. Live WeChat/Tencent credentials should be wired through environment variables but not required for unit tests.

---

## Task 1: Project Hygiene and Local Test Harness

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `requirements-dev.txt`
- Create: `requirements.txt`

- [ ] **Step 1: Create `.gitignore`**

Write exactly:

```gitignore
.DS_Store
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
.env
.env.*
!.env.example
.superpowers/
data/cache/
data/output/
```

- [ ] **Step 2: Create `requirements-dev.txt`**

Write exactly:

```text
pytest==8.4.1
```

- [ ] **Step 3: Create `requirements.txt`**

Write exactly:

```text
tencentcloud-sdk-python==3.0.1377
```

- [ ] **Step 4: Create `README.md`**

Write this content:

```markdown
# 每日精美文摘小程序

这是一个微信小程序 MVP 项目，用于验证“每天自动更新一篇精美短文摘，用户打开即可阅读，并可回看历史”的核心体验。

## 当前目标

- 固定公开来源采集素材。
- 规则清洗正文并修正文段。
- 使用云 OCR API 辅助识别图片文字。
- 抓取失败时从素材池补发。
- 将每日文摘发布到微信云数据库。
- 微信小程序展示今日文摘、历史列表和详情页。

## 本地测试

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## 本地 dry run

```bash
python3 scripts/build_daily_excerpt.py --dry-run --date 2026-06-28
```

Dry run 会把输出写入 `data/output/`，不会调用微信云数据库。

## 环境变量

生产发布时使用：

- `WECHAT_CLOUD_ENV_ID`
- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `TENCENT_OCR_REGION`

不要把真实密钥提交到仓库。
```

- [ ] **Step 5: Run status check**

Run:

```bash
git status --short
```

Expected: new hygiene files are untracked, and existing user files remain unmodified.

- [ ] **Step 6: Commit**

Run:

```bash
git add .gitignore README.md requirements-dev.txt requirements.txt
git commit -m "chore: add project hygiene and test harness"
```

Expected: commit succeeds and only the four files are included.

---

## Task 2: Text Cleaning Module

**Files:**
- Create: `scripts/excerpt_pipeline/__init__.py`
- Create: `scripts/excerpt_pipeline/cleaning.py`
- Create: `tests/test_cleaning.py`

- [ ] **Step 1: Create package marker**

Create `scripts/excerpt_pipeline/__init__.py` as an empty file.

- [ ] **Step 2: Write failing tests**

Create `tests/test_cleaning.py`:

```python
from scripts.excerpt_pipeline.cleaning import (
    build_summary,
    clean_text,
    content_hash,
    rebuild_paragraphs,
    split_sentences,
)


def test_clean_text_removes_html_and_extra_space():
    raw = "  <p>生活是自己的</p>\\n\\n\\n  #阅读  小红书  "
    assert clean_text(raw) == "生活是自己的\\n#阅读 小红书"


def test_split_sentences_handles_chinese_punctuation():
    text = "生活是自己的。不要活在别人的眼里！慢慢来，也是在抵达"
    assert split_sentences(text) == [
        "生活是自己的。",
        "不要活在别人的眼里！",
        "慢慢来，也是在抵达",
    ]


def test_rebuild_paragraphs_uses_ocr_line_breaks_as_hints():
    html_text = "生活是自己的。不要活在别人的眼里。有人三分钟泡面，有人三小时煲汤。每一步都值得被肯定。"
    ocr_text = "生活是自己的。\\n不要活在别人的眼里。\\n\\n有人三分钟泡面，有人三小时煲汤。\\n每一步都值得被肯定。"

    assert rebuild_paragraphs(html_text, ocr_text, min_paragraph_len=12, max_paragraph_len=36) == [
        "生活是自己的。不要活在别人的眼里。",
        "有人三分钟泡面，有人三小时煲汤。每一步都值得被肯定。",
    ]


def test_rebuild_paragraphs_without_ocr_splits_long_text():
    text = "生活是自己的。不要活在别人的眼里。每个人都有自己的节奏。慢慢走，也是在认真抵达。"
    assert rebuild_paragraphs(text, "", min_paragraph_len=12, max_paragraph_len=32) == [
        "生活是自己的。不要活在别人的眼里。",
        "每个人都有自己的节奏。慢慢走，也是在认真抵达。",
    ]


def test_build_summary_limits_length():
    paragraphs = ["生活是自己的。不要活在别人的眼里。", "慢慢来，也是在认真抵达。"]
    assert build_summary(paragraphs, limit=18) == "生活是自己的。不要活在别人..."


def test_content_hash_is_stable_for_same_content():
    first = content_hash("标题", ["第一段", "第二段"])
    second = content_hash("标题", ["第一段", "第二段"])
    assert first == second
    assert len(first) == 16
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_cleaning.py -v
```

Expected: FAIL with `ModuleNotFoundError` or missing functions in `scripts.excerpt_pipeline.cleaning`.

- [ ] **Step 4: Implement `cleaning.py`**

Create `scripts/excerpt_pipeline/cleaning.py`:

```python
import hashlib
import html
import re
from typing import Iterable, List


NOISE_PATTERNS = [
    r"登录后推荐更懂你的笔记",
    r"3 亿人的生活经验，都在小红书",
]


def clean_text(value: str) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\r\n?", "\n", text)
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, "", text)
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def split_sentences(text: str) -> List[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[。！？!?；;])\s*|\n+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _ocr_paragraph_sentence_counts(ocr_text: str) -> List[int]:
    text = clean_text(ocr_text)
    if not text:
        return []
    blocks = re.split(r"\n\s*\n", text)
    counts = []
    for block in blocks:
        count = len(split_sentences(block))
        if count:
            counts.append(count)
    return counts


def _append_or_flush(paragraphs: List[str], current: List[str], max_paragraph_len: int) -> List[str]:
    if not current:
        return []
    paragraph = "".join(current).strip()
    if paragraph:
        paragraphs.append(paragraph)
    return []


def rebuild_paragraphs(
    html_text: str,
    ocr_text: str = "",
    *,
    min_paragraph_len: int = 24,
    max_paragraph_len: int = 80,
) -> List[str]:
    sentences = split_sentences(html_text)
    if not sentences:
        sentences = split_sentences(ocr_text)
    if not sentences:
        return []

    counts = _ocr_paragraph_sentence_counts(ocr_text)
    if counts and sum(counts) <= len(sentences):
        paragraphs = []
        index = 0
        for count in counts:
            chunk = sentences[index:index + count]
            if chunk:
                paragraphs.append("".join(chunk))
            index += count
        if index < len(sentences):
            paragraphs.append("".join(sentences[index:]))
        return _merge_short_paragraphs(paragraphs, min_paragraph_len)

    paragraphs: List[str] = []
    current: List[str] = []
    for sentence in sentences:
        next_text = "".join(current) + sentence
        if current and len(next_text) > max_paragraph_len:
            current = _append_or_flush(paragraphs, current, max_paragraph_len)
        current.append(sentence)
    _append_or_flush(paragraphs, current, max_paragraph_len)
    return _merge_short_paragraphs(paragraphs, min_paragraph_len)


def _merge_short_paragraphs(paragraphs: Iterable[str], min_paragraph_len: int) -> List[str]:
    result: List[str] = []
    buffer = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if not buffer:
            buffer = paragraph
        elif len(buffer) < min_paragraph_len:
            buffer += paragraph
        else:
            result.append(buffer)
            buffer = paragraph
    if buffer:
        result.append(buffer)
    return result


def build_summary(paragraphs: List[str], limit: int = 48) -> str:
    text = clean_text("".join(paragraphs))
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def content_hash(title: str, paragraphs: List[str]) -> str:
    payload = clean_text(title) + "\n" + "\n".join(clean_text(item) for item in paragraphs)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_cleaning.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add scripts/excerpt_pipeline/__init__.py scripts/excerpt_pipeline/cleaning.py tests/test_cleaning.py
git commit -m "feat: add excerpt text cleaning"
```

Expected: commit succeeds.

---

## Task 3: Material Pool Fallback

**Files:**
- Create: `scripts/excerpt_pipeline/material_pool.py`
- Create: `data/material_pool/seed.json`
- Create: `tests/test_material_pool.py`

- [ ] **Step 1: Write seed fallback material**

Create `data/material_pool/seed.json`:

```json
[
  {
    "id": "seed-20260628-001",
    "title": "生活是自己的",
    "paragraphs": [
      "生活从来不在别人嘴里，而在自己心里。",
      "与其在意他人眼光，不如专注自己脚下。每一步都值得被肯定。"
    ],
    "summary": "生活从来不在别人嘴里，而在自己心里。",
    "source_name": "欣欣的阅读疗愈记",
    "source_url": "",
    "content_hash": "seed-001",
    "status": "candidate",
    "created_at": "2026-06-28T00:00:00Z",
    "used_at": ""
  }
]
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_material_pool.py`:

```python
import json

from scripts.excerpt_pipeline.material_pool import load_material_pool, select_fallback_material


def test_load_material_pool_reads_list(tmp_path):
    path = tmp_path / "pool.json"
    path.write_text(json.dumps([{"id": "a", "status": "candidate"}]), encoding="utf-8")
    assert load_material_pool(path) == [{"id": "a", "status": "candidate"}]


def test_load_material_pool_missing_file_returns_empty_list(tmp_path):
    assert load_material_pool(tmp_path / "missing.json") == []


def test_select_fallback_material_skips_used_and_duplicate_hash():
    pool = [
        {"id": "used", "status": "used", "content_hash": "a"},
        {"id": "duplicate", "status": "candidate", "content_hash": "b"},
        {"id": "fresh", "status": "candidate", "content_hash": "c"},
    ]
    selected = select_fallback_material(pool, published_hashes={"b"})
    assert selected["id"] == "fresh"


def test_select_fallback_material_returns_none_when_empty():
    assert select_fallback_material([], published_hashes=set()) is None
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_material_pool.py -v
```

Expected: FAIL because `scripts.excerpt_pipeline.material_pool` does not exist.

- [ ] **Step 4: Implement material pool module**

Create `scripts/excerpt_pipeline/material_pool.py`:

```python
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


Material = Dict[str, Any]


def load_material_pool(path: Path) -> List[Material]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"material pool must be a list: {path}")
    return [item for item in data if isinstance(item, dict)]


def select_fallback_material(
    materials: Iterable[Material],
    *,
    published_hashes: Set[str],
) -> Optional[Material]:
    for material in materials:
        if material.get("status") != "candidate":
            continue
        if material.get("content_hash") in published_hashes:
            continue
        return material
    return None
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_material_pool.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add scripts/excerpt_pipeline/material_pool.py data/material_pool/seed.json tests/test_material_pool.py
git commit -m "feat: add fallback material pool"
```

Expected: commit succeeds.

---

## Task 4: Reusable Xiaohongshu Extraction Adapter

**Files:**
- Modify: `scripts/fetch_xiaohongshu_note.py`
- Modify: `scripts/fetch_xiaohongshu_user_posts.py`
- Create: `tests/fixtures/xiaohongshu-note.html`
- Create: `tests/test_xiaohongshu_extractors.py`

- [ ] **Step 1: Create fixture from existing raw HTML**

Run:

```bash
mkdir -p tests/fixtures
cp data/raw/xiaohongshu-c80cf3e1ef14.html tests/fixtures/xiaohongshu-note.html
```

Expected: fixture file exists.

- [ ] **Step 2: Write tests for existing extractors**

Create `tests/test_xiaohongshu_extractors.py`:

```python
from pathlib import Path

from scripts.fetch_xiaohongshu_note import extract_note
from scripts.fetch_xiaohongshu_user_posts import extract_profile_posts


FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_note_from_fixture():
    html_text = (FIXTURES / "xiaohongshu-note.html").read_text(encoding="utf-8")
    note = extract_note(
        html_text,
        "https://www.xiaohongshu.com/explore/example",
        "欣欣的阅读疗愈记",
    )
    assert note["parse_status"] == "ok"
    assert note["title"]
    assert note["content"]
    assert note["material_notes"]["phrase_candidates"]


def test_extract_profile_posts_accepts_raw_path(tmp_path):
    html_text = (Path("data/raw/xiaohongshu-user-profile.html")).read_text(encoding="utf-8")
    raw_path = Path("data/raw/xiaohongshu-user-profile.html")
    result = extract_profile_posts(
        html_text=html_text,
        profile_url="https://www.xiaohongshu.com/user/profile/5c1db0ab0000000005013197",
        expected_account="欣欣的阅读疗愈记",
        http_status=200,
        raw_path=raw_path,
    )
    assert result["parse_status"] == "ok"
    assert result["profile"]["nickname"] == "欣欣的阅读疗愈记"
    assert len(result["posts"]) >= 1
```

- [ ] **Step 3: Run tests**

Run:

```bash
python3 -m pytest tests/test_xiaohongshu_extractors.py -v
```

Expected: tests pass without code changes. If they fail because `raw_path.relative_to(PROJECT_ROOT)` rejects relative paths, change the test `raw_path` to `Path.cwd() / "data/raw/xiaohongshu-user-profile.html"` and run again.

- [ ] **Step 4: Add explicit reusable comments only if needed**

If tests pass, do not modify the extractor scripts. If comments are needed, add this one-line comment above `extract_note` and `extract_profile_posts`:

```python
# Used by both the CLI and the automated daily excerpt pipeline.
```

- [ ] **Step 5: Commit**

Run:

```bash
git add tests/fixtures/xiaohongshu-note.html tests/test_xiaohongshu_extractors.py scripts/fetch_xiaohongshu_note.py scripts/fetch_xiaohongshu_user_posts.py
git commit -m "test: cover xiaohongshu extraction fixtures"
```

Expected: commit succeeds. If extractor scripts were unchanged, Git commits only test files and fixture.

---

## Task 5: OCR Abstraction

**Files:**
- Create: `scripts/excerpt_pipeline/ocr.py`
- Create: `tests/test_ocr.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ocr.py`:

```python
import os

from scripts.excerpt_pipeline.ocr import FakeOcrClient, create_ocr_client


def test_fake_ocr_returns_empty_text_for_missing_images():
    client = FakeOcrClient()
    assert client.extract_texts([]) == []


def test_fake_ocr_returns_seed_texts():
    client = FakeOcrClient(seed_texts=["第一行", "第二行"])
    assert client.extract_texts(["a.jpg", "b.jpg"]) == ["第一行", "第二行"]


def test_create_ocr_client_without_credentials_returns_fake(monkeypatch):
    for key in ["TENCENT_SECRET_ID", "TENCENT_SECRET_KEY"]:
        monkeypatch.delenv(key, raising=False)
    assert isinstance(create_ocr_client(), FakeOcrClient)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_ocr.py -v
```

Expected: FAIL because `scripts.excerpt_pipeline.ocr` does not exist.

- [ ] **Step 3: Implement OCR module**

Create `scripts/excerpt_pipeline/ocr.py`:

```python
import base64
import os
import urllib.request
from dataclasses import dataclass
from typing import Iterable, List, Protocol


class OcrClient(Protocol):
    def extract_texts(self, image_urls: Iterable[str]) -> List[str]:
        ...


@dataclass
class FakeOcrClient:
    seed_texts: List[str] | None = None

    def extract_texts(self, image_urls: Iterable[str]) -> List[str]:
        urls = list(image_urls)
        if self.seed_texts is None:
            return []
        return self.seed_texts[: len(urls)]


class TencentOcrClient:
    def __init__(self, secret_id: str, secret_key: str, region: str = "ap-guangzhou") -> None:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.ocr.v20181119 import ocr_client

        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "ocr.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        self._client = ocr_client.OcrClient(cred, region, client_profile)

    def extract_texts(self, image_urls: Iterable[str]) -> List[str]:
        from tencentcloud.ocr.v20181119 import models

        results: List[str] = []
        for image_url in image_urls:
            request = models.GeneralBasicOCRRequest()
            if image_url.startswith(("http://", "https://")):
                request.ImageUrl = image_url
            else:
                with urllib.request.urlopen(image_url, timeout=20) as response:
                    request.ImageBase64 = base64.b64encode(response.read()).decode("ascii")
            response = self._client.GeneralBasicOCR(request)
            words = [item.DetectedText for item in response.TextDetections]
            results.append("\n".join(words))
        return results


def create_ocr_client() -> OcrClient:
    secret_id = os.getenv("TENCENT_SECRET_ID", "")
    secret_key = os.getenv("TENCENT_SECRET_KEY", "")
    region = os.getenv("TENCENT_OCR_REGION", "ap-guangzhou")
    if not secret_id or not secret_key:
        return FakeOcrClient()
    return TencentOcrClient(secret_id, secret_key, region)
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_ocr.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/excerpt_pipeline/ocr.py tests/test_ocr.py
git commit -m "feat: add OCR client abstraction"
```

Expected: commit succeeds.

---

## Task 6: Local Publisher and Daily Pipeline Dry Run

**Files:**
- Create: `scripts/excerpt_pipeline/models.py`
- Create: `scripts/excerpt_pipeline/publishers.py`
- Create: `scripts/build_daily_excerpt.py`
- Create: `config/sources.json`
- Create: `tests/test_build_daily_excerpt.py`

- [ ] **Step 1: Create source config**

Create `config/sources.json`:

```json
[
  {
    "id": "xiaohongshu-xinxin",
    "name": "欣欣的阅读疗愈记",
    "platform": "xiaohongshu",
    "profile_url": "https://www.xiaohongshu.com/user/profile/5c1db0ab0000000005013197",
    "enabled": true
  }
]
```

- [ ] **Step 2: Write failing integration test**

Create `tests/test_build_daily_excerpt.py`:

```python
import json
import subprocess
from pathlib import Path


def test_build_daily_excerpt_dry_run_outputs_excerpt_and_log(tmp_path):
    output_dir = tmp_path / "output"
    result = subprocess.run(
        [
            "python3",
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
```

- [ ] **Step 3: Run test to verify failure**

Run:

```bash
python3 -m pytest tests/test_build_daily_excerpt.py -v
```

Expected: FAIL because `scripts/build_daily_excerpt.py` does not exist.

- [ ] **Step 4: Create models**

Create `scripts/excerpt_pipeline/models.py`:

```python
from datetime import datetime, timezone
from typing import Any, Dict, List


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_excerpt(
    *,
    date: str,
    title: str,
    paragraphs: List[str],
    summary: str,
    source_name: str,
    source_url: str,
    source_account_id: str,
    content_hash: str,
    publish_type: str,
) -> Dict[str, Any]:
    return {
        "date": date,
        "title": title,
        "paragraphs": paragraphs,
        "summary": summary,
        "source_name": source_name,
        "source_url": source_url,
        "source_account_id": source_account_id,
        "content_hash": content_hash,
        "publish_type": publish_type,
        "status": "published",
        "created_at": utc_now(),
    }


def make_job_log(
    *,
    date: str,
    status: str,
    source_name: str,
    excerpt_id: str = "",
    fallback_material_id: str = "",
    message: str = "",
    error_detail: str = "",
) -> Dict[str, Any]:
    return {
        "date": date,
        "status": status,
        "source_name": source_name,
        "excerpt_id": excerpt_id,
        "fallback_material_id": fallback_material_id,
        "message": message,
        "error_detail": error_detail,
        "created_at": utc_now(),
    }
```

- [ ] **Step 5: Create publishers**

Create `scripts/excerpt_pipeline/publishers.py`:

```python
import json
from pathlib import Path
from typing import Any, Dict, List, Protocol


class Publisher(Protocol):
    def publish_excerpt(self, excerpt: Dict[str, Any]) -> str:
        ...

    def publish_job_log(self, log: Dict[str, Any]) -> str:
        ...


class LocalJsonPublisher:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def publish_excerpt(self, excerpt: Dict[str, Any]) -> str:
        return self._append("excerpts.json", excerpt)

    def publish_job_log(self, log: Dict[str, Any]) -> str:
        return self._append("job_logs.json", log)

    def _append(self, filename: str, item: Dict[str, Any]) -> str:
        path = self.output_dir / filename
        if path.exists():
            data: List[Dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = []
        item_id = item.get("_id") or f"local-{len(data) + 1}"
        item["_id"] = item_id
        data.append(item)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return item_id
```

- [ ] **Step 6: Create CLI pipeline**

Create `scripts/build_daily_excerpt.py`:

```python
#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Set

from fetch_xiaohongshu_note import extract_note
from excerpt_pipeline.cleaning import build_summary, content_hash, rebuild_paragraphs
from excerpt_pipeline.material_pool import load_material_pool, select_fallback_material
from excerpt_pipeline.models import make_excerpt, make_job_log
from excerpt_pipeline.ocr import create_ocr_client
from excerpt_pipeline.publishers import LocalJsonPublisher


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and publish the daily excerpt.")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "data" / "output"))
    parser.add_argument("--material-pool", default=str(PROJECT_ROOT / "data" / "material_pool" / "seed.json"))
    parser.add_argument("--raw-note-html", default="")
    args = parser.parse_args()

    publisher = LocalJsonPublisher(Path(args.output_dir))
    published_hashes: Set[str] = _load_published_hashes(Path(args.output_dir) / "excerpts.json")
    material_pool = load_material_pool(Path(args.material_pool))

    try:
        excerpt = _build_from_raw_note(args.date, Path(args.raw_note_html)) if args.raw_note_html else None
        if excerpt and excerpt["content_hash"] not in published_hashes:
            excerpt_id = publisher.publish_excerpt(excerpt)
            log = make_job_log(
                date=args.date,
                status="success",
                source_name=excerpt["source_name"],
                excerpt_id=excerpt_id,
                message="published fresh excerpt",
            )
            publisher.publish_job_log(log)
            print(f"published excerpt {excerpt_id}")
            return 0
        fallback = select_fallback_material(material_pool, published_hashes=published_hashes)
        if not fallback:
            log = make_job_log(
                date=args.date,
                status="failed",
                source_name="",
                message="no fresh content and no fallback material",
            )
            publisher.publish_job_log(log)
            print("no excerpt published")
            return 1
        excerpt = make_excerpt(
            date=args.date,
            title=fallback["title"],
            paragraphs=fallback["paragraphs"],
            summary=fallback["summary"],
            source_name=fallback.get("source_name", ""),
            source_url=fallback.get("source_url", ""),
            source_account_id="",
            content_hash=fallback["content_hash"],
            publish_type="fallback",
        )
        excerpt_id = publisher.publish_excerpt(excerpt)
        publisher.publish_job_log(
            make_job_log(
                date=args.date,
                status="fallback_used",
                source_name=excerpt["source_name"],
                excerpt_id=excerpt_id,
                fallback_material_id=fallback.get("id", ""),
                message="used fallback material",
            )
        )
        print(f"published excerpt {excerpt_id}")
        return 0
    except Exception as exc:
        publisher.publish_job_log(
            make_job_log(
                date=args.date,
                status="failed",
                source_name="",
                message="pipeline failed",
                error_detail=str(exc),
            )
        )
        raise


def _build_from_raw_note(date: str, raw_note_html: Path) -> Dict[str, Any] | None:
    if not raw_note_html.exists():
        return None
    html_text = raw_note_html.read_text(encoding="utf-8")
    note = extract_note(html_text, "local-fixture", "欣欣的阅读疗愈记")
    if note.get("parse_status") != "ok":
        return None
    ocr_texts = create_ocr_client().extract_texts(note.get("image_urls", []))
    paragraphs = rebuild_paragraphs(note.get("content", ""), "\n\n".join(ocr_texts))
    if not paragraphs:
        return None
    title = note.get("title") or "每日文摘"
    return make_excerpt(
        date=date,
        title=title,
        paragraphs=paragraphs,
        summary=build_summary(paragraphs),
        source_name=note.get("account_name") or note.get("expected_account_name") or "",
        source_url=note.get("note_url") or "",
        source_account_id="xiaohongshu-xinxin",
        content_hash=content_hash(title, paragraphs),
        publish_type="fresh",
    )


def _load_published_hashes(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item.get("content_hash", "") for item in data if isinstance(item, dict)}


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run test to verify pass**

Run:

```bash
python3 -m pytest tests/test_build_daily_excerpt.py -v
```

Expected: test passes.

- [ ] **Step 8: Run dry run manually**

Run:

```bash
python3 scripts/build_daily_excerpt.py --dry-run --date 2026-06-28 --raw-note-html data/raw/xiaohongshu-c80cf3e1ef14.html
```

Expected: stdout includes `published excerpt`, and `data/output/excerpts.json` plus `data/output/job_logs.json` exist.

- [ ] **Step 9: Commit**

Run:

```bash
git add config/sources.json scripts/excerpt_pipeline/models.py scripts/excerpt_pipeline/publishers.py scripts/build_daily_excerpt.py tests/test_build_daily_excerpt.py
git commit -m "feat: add daily excerpt dry-run pipeline"
```

Expected: commit succeeds.

---

## Task 7: GitHub Actions Scheduled Dry Run

**Files:**
- Create: `.github/workflows/daily-excerpt.yml`

- [ ] **Step 1: Create workflow**

Create `.github/workflows/daily-excerpt.yml`:

```yaml
name: Daily Excerpt

on:
  workflow_dispatch:
  schedule:
    - cron: "10 22 * * *"

jobs:
  build-daily-excerpt:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r requirements-dev.txt

      - name: Run tests
        run: pytest

      - name: Build daily excerpt dry run
        env:
          TENCENT_SECRET_ID: ${{ secrets.TENCENT_SECRET_ID }}
          TENCENT_SECRET_KEY: ${{ secrets.TENCENT_SECRET_KEY }}
          TENCENT_OCR_REGION: ${{ secrets.TENCENT_OCR_REGION }}
        run: |
          python scripts/build_daily_excerpt.py \
            --dry-run \
            --raw-note-html data/raw/xiaohongshu-c80cf3e1ef14.html

      - name: Upload dry-run output
        uses: actions/upload-artifact@v4
        with:
          name: daily-excerpt-output
          path: data/output/
```

- [ ] **Step 2: Run local YAML sanity check**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path(".github/workflows/daily-excerpt.yml").read_text()
assert "workflow_dispatch" in text
assert "schedule" in text
assert "pytest" in text
print("workflow sanity ok")
PY
```

Expected: prints `workflow sanity ok`.

- [ ] **Step 3: Commit**

Run:

```bash
git add .github/workflows/daily-excerpt.yml
git commit -m "ci: add daily excerpt workflow"
```

Expected: commit succeeds.

---

## Task 8: WeChat Cloud Publisher Placeholder

**Files:**
- Modify: `scripts/excerpt_pipeline/publishers.py`
- Create: `tests/test_publishers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_publishers.py`:

```python
import pytest

from scripts.excerpt_pipeline.publishers import WeChatCloudPublisher


def test_wechat_publisher_requires_credentials():
    with pytest.raises(ValueError, match="WECHAT_CLOUD_ENV_ID"):
        WeChatCloudPublisher(env_id="", app_id="", app_secret="")


def test_wechat_publisher_builds_database_payload():
    publisher = WeChatCloudPublisher(
        env_id="env",
        app_id="app",
        app_secret="secret",
        access_token="token",
    )
    payload = publisher.build_add_payload("excerpts", {"title": "每日文摘"})
    assert payload["env"] == "env"
    assert payload["query"] == 'db.collection("excerpts").add({"data":{"title":"每日文摘"}})'
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_publishers.py -v
```

Expected: FAIL because `WeChatCloudPublisher` does not exist.

- [ ] **Step 3: Implement publisher class without live network in tests**

Append to `scripts/excerpt_pipeline/publishers.py`:

```python
import os
import urllib.parse
import urllib.request


class WeChatCloudPublisher:
    def __init__(
        self,
        *,
        env_id: str | None = None,
        app_id: str | None = None,
        app_secret: str | None = None,
        access_token: str | None = None,
    ) -> None:
        self.env_id = env_id if env_id is not None else os.getenv("WECHAT_CLOUD_ENV_ID", "")
        self.app_id = app_id if app_id is not None else os.getenv("WECHAT_APP_ID", "")
        self.app_secret = app_secret if app_secret is not None else os.getenv("WECHAT_APP_SECRET", "")
        self.access_token = access_token
        missing = []
        if not self.env_id:
            missing.append("WECHAT_CLOUD_ENV_ID")
        if not self.app_id:
            missing.append("WECHAT_APP_ID")
        if not self.app_secret:
            missing.append("WECHAT_APP_SECRET")
        if missing:
            raise ValueError(f"missing WeChat credentials: {', '.join(missing)}")

    def publish_excerpt(self, excerpt: Dict[str, Any]) -> str:
        return self._database_add("excerpts", excerpt)

    def publish_job_log(self, log: Dict[str, Any]) -> str:
        return self._database_add("job_logs", log)

    def build_add_payload(self, collection: str, data: Dict[str, Any]) -> Dict[str, str]:
        document = json.dumps({"data": data}, ensure_ascii=False, separators=(",", ":"))
        return {
            "env": self.env_id,
            "query": f'db.collection("{collection}").add({document})',
        }

    def _database_add(self, collection: str, data: Dict[str, Any]) -> str:
        token = self.access_token or self._get_access_token()
        payload = json.dumps(self.build_add_payload(collection, data), ensure_ascii=False).encode("utf-8")
        url = "https://api.weixin.qq.com/tcb/databaseadd?" + urllib.parse.urlencode({"access_token": token})
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        if body.get("errcode", 0) != 0:
            raise RuntimeError(f"WeChat databaseadd failed: {body}")
        return body.get("id_list", [""])[0]

    def _get_access_token(self) -> str:
        query = urllib.parse.urlencode(
            {
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            }
        )
        with urllib.request.urlopen(f"https://api.weixin.qq.com/cgi-bin/token?{query}", timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        token = body.get("access_token")
        if not token:
            raise RuntimeError(f"WeChat token request failed: {body}")
        return token
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
python3 -m pytest tests/test_publishers.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/excerpt_pipeline/publishers.py tests/test_publishers.py
git commit -m "feat: add WeChat cloud publisher"
```

Expected: commit succeeds.

---

## Task 9: Mini Program Shell and Pages

**Files:**
- Create: `miniprogram/project.config.json`
- Create: `miniprogram/app.js`
- Create: `miniprogram/app.json`
- Create: `miniprogram/app.wxss`
- Create: `miniprogram/utils/excerpts.js`
- Create: `miniprogram/pages/today/today.js`
- Create: `miniprogram/pages/today/today.wxml`
- Create: `miniprogram/pages/today/today.wxss`
- Create: `miniprogram/pages/history/history.js`
- Create: `miniprogram/pages/history/history.wxml`
- Create: `miniprogram/pages/history/history.wxss`
- Create: `miniprogram/pages/detail/detail.js`
- Create: `miniprogram/pages/detail/detail.wxml`
- Create: `miniprogram/pages/detail/detail.wxss`

- [ ] **Step 1: Create project config**

Create `miniprogram/project.config.json`:

```json
{
  "appid": "touristappid",
  "projectname": "daily-excerpt",
  "miniprogramRoot": "./",
  "setting": {
    "urlCheck": true,
    "es6": true,
    "enhance": true,
    "postcss": true,
    "minified": true
  },
  "compileType": "miniprogram"
}
```

- [ ] **Step 2: Create app files**

Create `miniprogram/app.js`:

```javascript
App({
  onLaunch() {
    if (wx.cloud) {
      wx.cloud.init({
        traceUser: false
      })
    }
  }
})
```

Create `miniprogram/app.json`:

```json
{
  "pages": [
    "pages/today/today",
    "pages/history/history",
    "pages/detail/detail"
  ],
  "window": {
    "navigationBarTitleText": "每日文摘",
    "navigationBarBackgroundColor": "#f7f3ed",
    "navigationBarTextStyle": "black",
    "backgroundColor": "#f7f3ed"
  },
  "tabBar": {
    "color": "#7a756d",
    "selectedColor": "#1f1d1a",
    "backgroundColor": "#f7f3ed",
    "borderStyle": "white",
    "list": [
      {
        "pagePath": "pages/today/today",
        "text": "今日"
      },
      {
        "pagePath": "pages/history/history",
        "text": "历史"
      }
    ]
  }
}
```

Create `miniprogram/app.wxss`:

```css
page {
  background: #f7f3ed;
  color: #1f1d1a;
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
}

.page {
  min-height: 100vh;
  box-sizing: border-box;
  padding: 40rpx 32rpx 64rpx;
}

.muted {
  color: #7a756d;
}
```

- [ ] **Step 3: Create data helper**

Create `miniprogram/utils/excerpts.js`:

```javascript
const db = wx.cloud.database()

async function getTodayExcerpt() {
  const result = await db.collection('excerpts')
    .where({ status: 'published' })
    .orderBy('date', 'desc')
    .limit(1)
    .get()
  return result.data[0] || null
}

async function getHistoryExcerpts(limit = 30) {
  const result = await db.collection('excerpts')
    .where({ status: 'published' })
    .orderBy('date', 'desc')
    .limit(limit)
    .get()
  return result.data
}

async function getExcerptById(id) {
  const result = await db.collection('excerpts').doc(id).get()
  return result.data
}

module.exports = {
  getTodayExcerpt,
  getHistoryExcerpts,
  getExcerptById
}
```

- [ ] **Step 4: Create today page**

Create `miniprogram/pages/today/today.js`:

```javascript
const { getTodayExcerpt } = require('../../utils/excerpts')

Page({
  data: {
    loading: true,
    excerpt: null,
    error: ''
  },

  onLoad() {
    this.loadExcerpt()
  },

  async loadExcerpt() {
    this.setData({ loading: true, error: '' })
    try {
      const excerpt = await getTodayExcerpt()
      this.setData({ excerpt, loading: false })
    } catch (error) {
      this.setData({ error: '暂时无法加载今日文摘', loading: false })
    }
  }
})
```

Create `miniprogram/pages/today/today.wxml`:

```xml
<view class="page">
  <view wx:if="{{loading}}" class="muted">加载中...</view>
  <view wx:elif="{{error}}" class="muted">{{error}}</view>
  <view wx:elif="{{!excerpt}}" class="muted">还没有可阅读的文摘</view>
  <view wx:else class="excerpt">
    <view class="date">{{excerpt.date}}</view>
    <view class="title">{{excerpt.title}}</view>
    <view class="source">来源：{{excerpt.source_name}}</view>
    <view class="paragraphs">
      <view wx:for="{{excerpt.paragraphs}}" wx:key="*this" class="paragraph">{{item}}</view>
    </view>
  </view>
</view>
```

Create `miniprogram/pages/today/today.wxss`:

```css
.date {
  color: #7a756d;
  font-size: 26rpx;
  margin-bottom: 24rpx;
}

.title {
  font-size: 44rpx;
  font-weight: 600;
  line-height: 1.35;
  margin-bottom: 18rpx;
}

.source {
  color: #7a756d;
  font-size: 26rpx;
  margin-bottom: 40rpx;
}

.paragraph {
  font-size: 34rpx;
  line-height: 1.9;
  margin-bottom: 28rpx;
}
```

- [ ] **Step 5: Create history page**

Create `miniprogram/pages/history/history.js`:

```javascript
const { getHistoryExcerpts } = require('../../utils/excerpts')

Page({
  data: {
    loading: true,
    excerpts: [],
    error: ''
  },

  onLoad() {
    this.loadHistory()
  },

  async loadHistory() {
    this.setData({ loading: true, error: '' })
    try {
      const excerpts = await getHistoryExcerpts()
      this.setData({ excerpts, loading: false })
    } catch (error) {
      this.setData({ error: '暂时无法加载历史文摘', loading: false })
    }
  },

  openDetail(event) {
    const id = event.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/detail/detail?id=${id}` })
  }
})
```

Create `miniprogram/pages/history/history.wxml`:

```xml
<view class="page">
  <view class="heading">历史文摘</view>
  <view wx:if="{{loading}}" class="muted">加载中...</view>
  <view wx:elif="{{error}}" class="muted">{{error}}</view>
  <view wx:elif="{{excerpts.length === 0}}" class="muted">暂无历史文摘</view>
  <view wx:else>
    <view wx:for="{{excerpts}}" wx:key="_id" class="history-item" data-id="{{item._id}}" bindtap="openDetail">
      <view class="item-date">{{item.date}}</view>
      <view class="item-title">{{item.title}}</view>
      <view class="item-summary">{{item.summary}}</view>
    </view>
  </view>
</view>
```

Create `miniprogram/pages/history/history.wxss`:

```css
.heading {
  font-size: 40rpx;
  font-weight: 600;
  margin-bottom: 32rpx;
}

.history-item {
  border-bottom: 1rpx solid rgba(31, 29, 26, 0.12);
  padding: 28rpx 0;
}

.item-date {
  color: #7a756d;
  font-size: 24rpx;
  margin-bottom: 10rpx;
}

.item-title {
  font-size: 32rpx;
  font-weight: 600;
  line-height: 1.45;
  margin-bottom: 12rpx;
}

.item-summary {
  color: #5e594f;
  font-size: 28rpx;
  line-height: 1.6;
}
```

- [ ] **Step 6: Create detail page**

Create `miniprogram/pages/detail/detail.js`:

```javascript
const { getExcerptById } = require('../../utils/excerpts')

Page({
  data: {
    loading: true,
    excerpt: null,
    error: ''
  },

  onLoad(options) {
    this.loadDetail(options.id)
  },

  async loadDetail(id) {
    if (!id) {
      this.setData({ loading: false, error: '缺少文摘 ID' })
      return
    }
    try {
      const excerpt = await getExcerptById(id)
      this.setData({ excerpt, loading: false })
    } catch (error) {
      this.setData({ error: '暂时无法加载文摘详情', loading: false })
    }
  }
})
```

Create `miniprogram/pages/detail/detail.wxml`:

```xml
<view class="page">
  <view wx:if="{{loading}}" class="muted">加载中...</view>
  <view wx:elif="{{error}}" class="muted">{{error}}</view>
  <view wx:elif="{{!excerpt}}" class="muted">文摘不存在</view>
  <view wx:else class="excerpt">
    <view class="date">{{excerpt.date}}</view>
    <view class="title">{{excerpt.title}}</view>
    <view class="source">来源：{{excerpt.source_name}}</view>
    <view class="paragraphs">
      <view wx:for="{{excerpt.paragraphs}}" wx:key="*this" class="paragraph">{{item}}</view>
    </view>
  </view>
</view>
```

Create `miniprogram/pages/detail/detail.wxss`:

```css
.date {
  color: #7a756d;
  font-size: 26rpx;
  margin-bottom: 24rpx;
}

.title {
  font-size: 44rpx;
  font-weight: 600;
  line-height: 1.35;
  margin-bottom: 18rpx;
}

.source {
  color: #7a756d;
  font-size: 26rpx;
  margin-bottom: 40rpx;
}

.paragraph {
  font-size: 34rpx;
  line-height: 1.9;
  margin-bottom: 28rpx;
}
```

- [ ] **Step 7: Validate Mini Program JSON files**

Run:

```bash
python3 -m json.tool miniprogram/app.json >/dev/null
python3 -m json.tool miniprogram/project.config.json >/dev/null
```

Expected: both commands exit 0.

- [ ] **Step 8: Commit**

Run:

```bash
git add miniprogram
git commit -m "feat: add minimal WeChat miniprogram"
```

Expected: commit succeeds.

---

## Task 10: Final Verification and Documentation Update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README with implementation status**

Append to `README.md`:

```markdown

## 微信小程序开发

用微信开发者工具打开 `miniprogram/` 目录。首次接入真实云开发环境时，需要：

1. 将 `miniprogram/project.config.json` 中的 `appid` 替换成真实小程序 AppID。
2. 在微信开发者工具中开通云开发。
3. 创建 `excerpts`、`sources`、`material_pool`、`job_logs` 集合。
4. 配置数据库权限，让普通用户只能读取 `status = "published"` 的文摘。
5. 在 GitHub Actions Secrets 中配置微信云开发和 OCR 凭据。

第一版可以先用 `python3 scripts/build_daily_excerpt.py --dry-run` 验证文摘生成，再接入真实微信云数据库发布。
```

- [ ] **Step 2: Run full Python tests**

Run:

```bash
python3 -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Run dry run**

Run:

```bash
rm -rf data/output
python3 scripts/build_daily_excerpt.py --dry-run --date 2026-06-28 --raw-note-html data/raw/xiaohongshu-c80cf3e1ef14.html
```

Expected: stdout includes `published excerpt`, and generated JSON contains one excerpt and one job log.

- [ ] **Step 4: Validate Mini Program JSON**

Run:

```bash
python3 -m json.tool miniprogram/app.json >/dev/null
python3 -m json.tool miniprogram/project.config.json >/dev/null
```

Expected: both commands exit 0.

- [ ] **Step 5: Check git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only intended implementation files are modified or untracked.

- [ ] **Step 6: Commit final docs**

Run:

```bash
git add README.md
git commit -m "docs: document miniprogram setup"
```

Expected: commit succeeds.

---

## Self-Review

Spec coverage:

- Minimal Mini Program today/history/detail pages: Task 9.
- GitHub Actions daily automation: Task 7.
- Fixed public source config: Task 6.
- HTML extraction reuse: Task 4 and Task 6.
- OCR-assisted paragraph correction: Task 5 and Task 6.
- Rule-based cleaning without required large model: Task 2 and Task 6.
- Fallback material: Task 3 and Task 6.
- Local logs and future cloud logs: Task 6 and Task 8.
- WeChat Cloud Database publisher: Task 8.
- Documentation and setup: Task 1 and Task 10.

Placeholder scan:

- The plan intentionally uses placeholder credential names and `touristappid`; both are explicit setup placeholders, not missing implementation details.
- No task says “write tests later” or “handle errors appropriately” without concrete code.

Type consistency:

- Excerpt fields match the design doc: `date`, `title`, `paragraphs`, `summary`, `source_name`, `source_url`, `source_account_id`, `content_hash`, `publish_type`, `status`, `created_at`.
- Job log fields match the design doc: `date`, `status`, `source_name`, `excerpt_id`, `fallback_material_id`, `message`, `error_detail`, `created_at`.
