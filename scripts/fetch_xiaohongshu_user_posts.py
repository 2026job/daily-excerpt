#!/usr/bin/env python3
"""
Fetch public Xiaohongshu posts from a user profile page.

The script is conservative: it reads public HTML/SSR data and does not bypass
login, signatures, CAPTCHAs, or private content. Xiaohongshu often exposes only
the first page to anonymous web requests; when more posts exist, the output
records the cursor and has_more flag for a later browser-authenticated crawler.
"""

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
EXTRACTED_DIR = PROJECT_ROOT / "data" / "extracted"

DEFAULT_USER_ID = "5c1db0ab0000000005013197"
DEFAULT_ACCOUNT = "欣欣的阅读疗愈记"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch public posts from a Xiaohongshu user profile."
    )
    parser.add_argument(
        "--user-id",
        default=DEFAULT_USER_ID,
        help=f"Xiaohongshu user id. Default: {DEFAULT_USER_ID}",
    )
    parser.add_argument(
        "--account",
        default=DEFAULT_ACCOUNT,
        help=f"Expected account name. Default: {DEFAULT_ACCOUNT}",
    )
    parser.add_argument(
        "--url",
        help="Full user profile URL. Overrides --user-id.",
    )
    parser.add_argument(
        "--out",
        default=str(EXTRACTED_DIR / "xiaohongshu-user-posts.json"),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--csv",
        default=str(EXTRACTED_DIR / "xiaohongshu-user-posts.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=8.0,
        help="Minimum delay before network requests, in seconds. Default: 8.",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=18.0,
        help="Maximum delay before network requests, in seconds. Default: 18.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Conservative retry count for transient network errors. Default: 2.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore an existing raw HTML cache and fetch again.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the target URL and risk controls without making a request.",
    )
    args = parser.parse_args()

    url = args.url or f"https://www.xiaohongshu.com/user/profile/{args.user_id}"
    if args.dry_run:
        print(f"目标 URL：{url}")
        print(f"请求延迟：{args.min_delay} 到 {args.max_delay} 秒")
        print(f"重试次数：{args.retries}")
        print("风控策略：命中登录/验证码/安全验证会停止，不做绕过。")
        return 0

    html_text, status, final_url, raw_path = load_or_fetch_html(
        url=url,
        timeout=args.timeout,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        retries=args.retries,
        use_cache=not args.no_cache,
    )

    result = extract_profile_posts(
        html_text=html_text,
        profile_url=final_url,
        expected_account=args.account,
        http_status=status,
        raw_path=raw_path,
    )

    json_path = write_json(args.out, result)
    csv_path = write_csv(args.csv, result["posts"])

    print(f"JSON 已保存：{json_path}")
    print(f"CSV 已保存：{csv_path}")
    print(f"账号：{result['profile'].get('nickname') or args.account}")
    print(f"本次抓到帖子：{len(result['posts'])} 条")
    print(f"是否还有更多：{result['pagination'].get('has_more')}")
    if result["pagination"].get("has_more"):
        print("提示：公开首屏显示还有更多；完整翻页通常需要浏览器登录态或小红书签名接口。")
    return 0


def load_or_fetch_html(
    url: str,
    timeout: int,
    min_delay: float,
    max_delay: float,
    retries: int,
    use_cache: bool,
) -> tuple[str, int, str, Path]:
    cache_path = raw_cache_path(url)
    if use_cache and cache_path.exists():
        html_text = cache_path.read_text(encoding="utf-8")
        return html_text, 200, url, cache_path

    delay = random.uniform(min_delay, max(min_delay, max_delay))
    print(f"低频保护：等待 {delay:.1f} 秒后请求公开主页...")
    time.sleep(delay)

    last_error = ""
    for attempt in range(retries + 1):
        try:
            html_text, status, final_url = fetch_html(url, timeout)
            raw_path = save_raw_html(final_url, html_text)
            if detect_failure(html_text) == "login_or_challenge":
                print("检测到登录、验证码或安全验证页面，已停止继续请求。", file=sys.stderr)
            return html_text, status, final_url, raw_path
        except SystemExit as exc:
            last_error = str(exc)
            if attempt >= retries:
                raise
            backoff = min(120.0, (2 ** attempt) * random.uniform(20.0, 45.0))
            print(f"请求失败，{backoff:.1f} 秒后保守重试：{last_error}", file=sys.stderr)
            time.sleep(backoff)

    raise SystemExit(last_error or "抓取失败")


def raw_cache_path(url: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return RAW_DIR / f"xiaohongshu-user-{digest}.html"


def fetch_html(url: str, timeout: int) -> tuple[str, int, str]:
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
            return body, response.status, response.geturl()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return body, exc.code, url
    except urllib.error.URLError as exc:
        raise SystemExit(f"抓取失败：{exc}") from exc


def save_raw_html(url: str, html_text: str) -> Path:
    path = raw_cache_path(url)
    path.write_text(html_text, encoding="utf-8")
    return path


def extract_profile_posts(
    html_text: str,
    profile_url: str,
    expected_account: str,
    http_status: int,
    raw_path: Path,
) -> Dict[str, Any]:
    state = extract_initial_state(html_text)
    user_state = state.get("user", {}) if isinstance(state, dict) else {}
    user_page = user_state.get("userPageData", {}) if isinstance(user_state, dict) else {}
    basic_info = user_page.get("basicInfo", {}) if isinstance(user_page, dict) else {}
    interactions = user_page.get("interactions", []) if isinstance(user_page, dict) else []
    note_queries = user_state.get("noteQueries", []) if isinstance(user_state, dict) else []
    note_tabs = user_state.get("notes", []) if isinstance(user_state, dict) else []
    first_tab = note_tabs[0] if note_tabs and isinstance(note_tabs[0], list) else []

    posts = []
    for index, item in enumerate(first_tab):
        card = item.get("noteCard", {}) if isinstance(item, dict) else {}
        post = normalize_post(card, item, profile_url, index)
        if post.get("title") or post.get("note_id") or post.get("cover_url"):
            posts.append(post)

    posts = dedupe_posts(posts)
    first_query = note_queries[0] if note_queries and isinstance(note_queries[0], dict) else {}

    return {
        "source": "小红书",
        "profile_url": profile_url,
        "expected_account_name": expected_account,
        "profile": {
            "nickname": basic_info.get("nickname") or expected_account,
            "red_id": basic_info.get("redId", ""),
            "ip_location": basic_info.get("ipLocation", ""),
            "description": basic_info.get("desc", ""),
            "avatar": basic_info.get("images") or basic_info.get("imageb", ""),
            "interactions": interactions,
        },
        "posts": posts,
        "pagination": {
            "has_more": bool(first_query.get("hasMore")),
            "cursor": first_query.get("cursor", ""),
            "page": first_query.get("page", 1),
            "page_size": first_query.get("num", ""),
            "visible_count": len(posts),
        },
        "parse_status": "ok" if posts else detect_failure(html_text),
        "http_status": http_status,
        "raw_html_path": str(raw_path.relative_to(PROJECT_ROOT)),
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "limitations": [
            "匿名公开主页通常只返回首屏笔记。",
            "完整翻页可能需要浏览器登录态、小红书接口签名或用户授权导出。",
            "本脚本不绕过登录、验证码、风控或私密内容限制。",
        ],
    }


def extract_initial_state(html_text: str) -> Dict[str, Any]:
    match = re.search(
        r"<script>window\.__INITIAL_STATE__=(.*?)</script>",
        html_text,
        flags=re.I | re.S,
    )
    if not match:
        return {}
    script = normalize_js_state(match.group(1))
    try:
        return json.loads(script)
    except json.JSONDecodeError:
        return {}


def normalize_js_state(script: str) -> str:
    script = html.unescape(script.strip())
    script = re.sub(r":undefined(?=[,}])", ":null", script)
    script = re.sub(r"\[undefined(?=[,\]])", "[null", script)
    script = re.sub(r",undefined(?=[,\]])", ",null", script)
    return script


def normalize_post(card: Dict[str, Any], wrapper: Dict[str, Any], profile_url: str, index: int) -> Dict[str, Any]:
    note_id = (
        card.get("noteId")
        or card.get("id")
        or wrapper.get("id")
        or extract_note_id_from_cover(card.get("cover", {}))
    )
    xsec_token = card.get("xsecToken") or wrapper.get("xsecToken") or ""
    title = card.get("displayTitle") or card.get("title") or ""
    user = card.get("user", {}) if isinstance(card.get("user"), dict) else {}
    interact = card.get("interactInfo", {}) if isinstance(card.get("interactInfo"), dict) else {}
    cover = card.get("cover", {}) if isinstance(card.get("cover"), dict) else {}

    return {
        "index": index,
        "note_id": note_id or "",
        "title": clean_text(title),
        "type": card.get("type", ""),
        "author_name": user.get("nickname") or user.get("nickName") or "",
        "author_id": user.get("userId", ""),
        "liked_count": interact.get("likedCount", ""),
        "sticky": bool(interact.get("sticky")),
        "cover_url": get_cover_url(cover),
        "width": cover.get("width", ""),
        "height": cover.get("height", ""),
        "xsec_token": xsec_token,
        "url": build_note_url(note_id, xsec_token, profile_url),
    }


def extract_note_id_from_cover(cover: Dict[str, Any]) -> str:
    for value in flatten(cover):
        if not isinstance(value, str):
            continue
        match = re.search(r"/([0-9a-f]{24})(?:!|/|$)", value)
        if match:
            return match.group(1)
    return ""


def get_cover_url(cover: Dict[str, Any]) -> str:
    if cover.get("urlDefault"):
        return cover["urlDefault"]
    info_list = cover.get("infoList", [])
    if isinstance(info_list, list):
        for item in info_list:
            if isinstance(item, dict) and item.get("url"):
                return item["url"]
    return cover.get("urlPre") or cover.get("url") or ""


def build_note_url(note_id: str, xsec_token: str, profile_url: str) -> str:
    if not note_id:
        return ""
    url = f"https://www.xiaohongshu.com/explore/{note_id}"
    params = {"xsec_token": xsec_token, "xsec_source": "pc_user"}
    query = "&".join(f"{key}={urllib_quote(value)}" for key, value in params.items() if value)
    return f"{url}?{query}" if query else url


def urllib_quote(value: str) -> str:
    return urllib.request.quote(value, safe="")


def dedupe_posts(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for post in posts:
        key = post.get("note_id") or f"{post.get('title')}::{post.get('cover_url')}"
        if key in seen:
            continue
        seen.add(key)
        result.append(post)
    return result


def detect_failure(html_text: str) -> str:
    challenge_signals = [
        "验证码",
        "安全验证",
        "访问频繁",
        "请稍后再试",
        "滑块验证",
        "risk",
    ]
    login_only = "登录后推荐更懂你的笔记" in html_text and "window.__INITIAL_STATE__" not in html_text
    if login_only or any(signal in html_text for signal in challenge_signals):
        return "login_or_challenge"
    return "blocked_or_unparsed"


def clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def flatten(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        for child in value.values():
            yield from flatten(child)
    elif isinstance(value, list):
        for child in value:
            yield from flatten(child)
    else:
        yield value


def write_json(path: str, data: Dict[str, Any]) -> Path:
    out_path = Path(path)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def write_csv(path: str, posts: List[Dict[str, Any]]) -> Path:
    out_path = Path(path)
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "index",
        "note_id",
        "title",
        "type",
        "author_name",
        "author_id",
        "liked_count",
        "sticky",
        "cover_url",
        "url",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(posts)
    return out_path


if __name__ == "__main__":
    raise SystemExit(main())
