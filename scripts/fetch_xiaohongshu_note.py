#!/usr/bin/env python3
"""
Fetch one public Xiaohongshu note page and extract a normalized JSON draft.

This script does not bypass login, CAPTCHAs, robots restrictions, or private
content. It is intended for material-preparation tests on public pages you can
open normally in a browser.
"""

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
EXTRACTED_DIR = PROJECT_ROOT / "data" / "extracted"

DEFAULT_ACCOUNT = "欣欣的阅读疗愈记"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and normalize one public Xiaohongshu note."
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Public Xiaohongshu note URL. Example: https://www.xiaohongshu.com/explore/...",
    )
    parser.add_argument(
        "--account",
        default=DEFAULT_ACCOUNT,
        help=f"Expected account name for metadata. Default: {DEFAULT_ACCOUNT}",
    )
    parser.add_argument(
        "--out",
        default=str(EXTRACTED_DIR / "xiaohongshu-note.json"),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds.",
    )
    args = parser.parse_args()

    if not args.url:
        print("需要提供一篇小红书笔记 URL。", file=sys.stderr)
        print("示例：python3 scripts/fetch_xiaohongshu_note.py 'https://www.xiaohongshu.com/explore/...'", file=sys.stderr)
        return 2

    url = normalize_url(args.url)
    html_text, status = fetch_html(url, args.timeout)
    raw_path = save_raw_html(url, html_text)
    note = extract_note(html_text, url, args.account)
    note["http_status"] = status
    note["raw_html_path"] = str(raw_path.relative_to(PROJECT_ROOT))
    note["fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat()

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"已保存：{out_path}")
    print(f"解析状态：{note['parse_status']}")
    if note.get("title"):
        print(f"标题：{note['title']}")
    if note.get("content"):
        preview = note["content"][:80].replace("\n", " ")
        print(f"正文预览：{preview}")
    if note["parse_status"] != "ok":
        print("提示：页面可能需要登录、动态渲染，或该 URL 不是公开笔记页。")
    return 0


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def fetch_html(url: str, timeout: int) -> tuple[str, int]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
            return body, response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return body, exc.code
    except urllib.error.URLError as exc:
        raise SystemExit(f"抓取失败：{exc}") from exc


def save_raw_html(url: str, html_text: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    path = RAW_DIR / f"xiaohongshu-{digest}.html"
    path.write_text(html_text, encoding="utf-8")
    return path


def extract_note(html_text: str, url: str, account_name: str) -> Dict[str, Any]:
    json_ld = extract_json_ld(html_text)
    next_data = extract_next_data(html_text)
    initial_state = extract_initial_state(html_text)
    og = extract_meta_tags(html_text)

    title = first_text(
        deep_find(initial_state, ["title", "displayTitle"]),
        deep_find(json_ld, ["headline", "name"]),
        deep_find(next_data, ["title", "displayTitle"]),
        [og.get("og:title"), og.get("twitter:title"), extract_title_tag(html_text)],
    )
    content = first_text(
        deep_find(initial_state, ["desc"]),
        [og.get("description")],
        deep_find(json_ld, ["articleBody", "description"]),
        deep_find(next_data, ["desc", "description", "content"]),
        [non_generic_description(og.get("og:description"))],
    )
    author = first_text(
        deep_find(initial_state, ["nickname", "userName", "authorName"]),
        deep_find(json_ld, ["author", "nickname", "userName", "name"]),
        deep_find(next_data, ["nickname", "userName", "authorName"]),
        [account_name],
    )
    image_urls = unique_strings(
        deep_find(initial_state, ["url", "urlDefault", "urlPre"])
        +
        deep_find(json_ld, ["image", "url"])
        + deep_find(next_data, ["url", "traceId"])
        + [og.get("og:image")]
    )
    tag_names = [
        item.get("name")
        for item in deep_find(initial_state, ["tagList"])
        if isinstance(item, dict)
    ]
    tags = unique_strings(tag_names + extract_hashtags(title or "") + extract_hashtags(content or ""))

    parse_status = "ok" if title or content else "blocked_or_unparsed"
    if looks_like_login_or_challenge(html_text):
        parse_status = "login_or_challenge"

    return {
        "source": "小红书",
        "expected_account_name": account_name,
        "account_name": clean_text(author),
        "note_url": url,
        "title": clean_title(title),
        "content": clean_text(content),
        "tags": tags,
        "image_urls": image_urls[:12],
        "parse_status": parse_status,
        "material_notes": build_material_notes(title, content),
    }


def extract_json_ld(html_text: str) -> List[Any]:
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        flags=re.I | re.S,
    )
    parsed = []
    for block in blocks:
        data = loads_json(html.unescape(strip_script_cdata(block)))
        if data is not None:
            parsed.append(data)
    return parsed


def extract_next_data(html_text: str) -> List[Any]:
    blocks = re.findall(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html_text,
        flags=re.I | re.S,
    )
    return [data for data in (loads_json(html.unescape(block)) for block in blocks) if data is not None]


def extract_initial_state(html_text: str) -> List[Any]:
    match = re.search(
        r"<script>window\.__INITIAL_STATE__=(.*?)</script>",
        html_text,
        flags=re.I | re.S,
    )
    if not match:
        return []
    data = loads_json(match.group(1))
    return [data] if data is not None else []


def extract_meta_tags(html_text: str) -> Dict[str, str]:
    tags: Dict[str, str] = {}
    pattern = re.compile(r"<meta\s+([^>]+)>", re.I | re.S)
    attr_pattern = re.compile(r'([:\w-]+)\s*=\s*(["\'])(.*?)\2', re.S)
    for match in pattern.finditer(html_text):
        attrs = {name.lower(): html.unescape(value) for name, _, value in attr_pattern.findall(match.group(1))}
        key = attrs.get("property") or attrs.get("name")
        if key and "content" in attrs:
            tags[key.lower()] = attrs["content"]
    return tags


def extract_title_tag(html_text: str) -> Optional[str]:
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.I | re.S)
    return html.unescape(match.group(1)) if match else None


def loads_json(value: str) -> Optional[Any]:
    try:
        return json.loads(value.strip())
    except json.JSONDecodeError:
        return None


def strip_script_cdata(value: str) -> str:
    return re.sub(r"^\s*//<!\[CDATA\[|\s*//\]\]>\s*$", "", value.strip())


def deep_find(value: Any, keys: Iterable[str]) -> List[Any]:
    found: List[Any] = []
    target_keys = set(keys)

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key in target_keys:
                    found.append(child)
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return found


def first_text(*groups: Iterable[Any]) -> Optional[str]:
    for group in groups:
        for value in flatten(group):
            if isinstance(value, dict):
                value = value.get("name") or value.get("nickname") or value.get("content")
            if isinstance(value, str) and clean_text(value):
                return value
    return None


def flatten(values: Iterable[Any]) -> Iterable[Any]:
    for value in values:
        if isinstance(value, list):
            yield from flatten(value)
        else:
            yield value


def clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def clean_title(value: Optional[str]) -> str:
    text = clean_text(value)
    text = re.sub(r"\s*-\s*小红书\s*$", "", text)
    return text.strip()


def non_generic_description(value: Optional[str]) -> Optional[str]:
    text = clean_text(value)
    generic_values = {"3 亿人的生活经验，都在小红书", "小红书"}
    return None if text in generic_values else text


def extract_hashtags(text: str) -> List[str]:
    if not text:
        return []
    return [item.strip("#＃ ") for item in re.findall(r"[#＃]([^#＃\s，。,.!?！？、]+)", text)]


def unique_strings(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in flatten(values):
        if not isinstance(value, str):
            continue
        value = clean_text(value)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def looks_like_login_or_challenge(html_text: str) -> bool:
    signals = ["登录", "验证码", "安全验证", "请稍后再试", "window.__INITIAL_STATE__"]
    return any(signal in html_text for signal in signals) and len(html_text) < 200_000


def build_material_notes(title: Optional[str], content: Optional[str]) -> Dict[str, Any]:
    text = clean_text("\n".join(item for item in [title, content] if item))
    sentences = split_sentences(text)
    phrase_candidates = [
        sentence for sentence in sentences if 8 <= len(sentence) <= 40 and not sentence.startswith("#")
    ]
    return {
        "phrase_candidates": phrase_candidates[:20],
        "suggested_categories": suggest_categories(text),
        "copyright_note": "建议仅用于内部风格分析或改写，不直接搬运原文入库。",
    }


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[。！？!?；;])\s*|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def suggest_categories(text: str) -> List[str]:
    mapping = {
        "治愈": ["疗愈", "治愈", "松弛", "接纳", "内耗", "情绪"],
        "励志": ["成长", "坚持", "改变", "自律", "行动"],
        "国风": ["诗", "山", "月", "茶", "书"],
        "人间烟火": ["生活", "日常", "烟火", "饭", "城市"],
        "晚安": ["晚安", "睡前", "夜", "月亮"],
    }
    categories = []
    for category, keywords in mapping.items():
        if any(keyword in text for keyword in keywords):
            categories.append(category)
    return categories or ["治愈"]


if __name__ == "__main__":
    raise SystemExit(main())
