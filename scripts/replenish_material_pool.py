#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from excerpt_pipeline.cleaning import build_summary, content_hash, rebuild_paragraphs
from excerpt_pipeline.material_pool import (
    append_unique_materials,
    load_material_pool,
    material_identity_keys,
    save_material_pool,
)
from excerpt_pipeline.models import normalize_image_urls, utc_now
from fetch_xiaohongshu_note import extract_note, fetch_html
from fetch_xiaohongshu_user_posts import (
    DEFAULT_ACCOUNT,
    DEFAULT_USER_ID,
    extract_profile_posts,
    load_or_fetch_html,
)


DEFAULT_PROFILE_URL = f"https://www.xiaohongshu.com/user/profile/{DEFAULT_USER_ID}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replenish the fallback material pool from a Xiaohongshu profile."
    )
    parser.add_argument(
        "--material-pool",
        default=str(PROJECT_ROOT / "data" / "material_pool" / "seed.json"),
    )
    parser.add_argument(
        "--candidate-pool",
        default=str(PROJECT_ROOT / "data" / "material_pool" / "xiaohongshu_candidates.json"),
    )
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "data" / "output"))
    parser.add_argument("--profile-url", default=DEFAULT_PROFILE_URL)
    parser.add_argument("--account", default=DEFAULT_ACCOUNT)
    parser.add_argument("--max-details", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    added = replenish_material_pool(
        pool_path=Path(args.material_pool),
        candidate_pool_path=Path(args.candidate_pool),
        output_dir=Path(args.output_dir),
        profile_url=args.profile_url,
        account=args.account,
        max_details=args.max_details,
        timeout=args.timeout,
    )
    print(f"added {added} material(s)")
    return 0


def replenish_material_pool(
    pool_path: Path,
    output_dir: Path,
    profile_url: str,
    account: str,
    max_details: int,
    timeout: int,
    candidate_pool_path: Optional[Path] = None,
) -> int:
    pool = load_material_pool(pool_path)
    candidate_pool_path = candidate_pool_path or pool_path.with_name("xiaohongshu_candidates.json")
    metadata_candidates = load_material_pool(candidate_pool_path)
    profile_result = load_profile_posts(profile_url, account, timeout)
    existing_keys = set()
    for material in pool:
        existing_keys.update(material_identity_keys(material))
    metadata_keys = set()
    for candidate in metadata_candidates:
        metadata_keys.update(material_identity_keys(candidate))

    added_materials = []
    added_metadata_candidates = []
    failed_candidates = []
    attempted = 0
    for post in profile_result.get("posts", []):
        if attempted >= max_details:
            break
        if _post_seen(post, existing_keys):
            continue

        attempted += 1
        note_url = post.get("url", "")
        if not note_url:
            metadata_candidate = metadata_candidate_from_post(post, profile_url)
            combined_candidates, added_candidates = append_unique_materials(
                metadata_candidates + added_metadata_candidates,
                [metadata_candidate],
            )
            if added_candidates and not (material_identity_keys(added_candidates[0]) & metadata_keys):
                added_metadata_candidates.append(added_candidates[0])
                metadata_keys.update(material_identity_keys(added_candidates[0]))
            else:
                metadata_candidates = combined_candidates
            failed_candidates.append(_failed_candidate(post, "missing note url"))
            continue

        try:
            html_text, _status = fetch_html(note_url, timeout)
            note = extract_note(html_text, note_url, account)
        except Exception as exc:
            failed_candidates.append(_failed_candidate(post, f"detail fetch failed: {exc}"))
            continue

        material, reason = material_from_note(note, post)
        if material is None:
            failed_candidates.append(_failed_candidate(post, reason))
            continue

        combined, added = append_unique_materials(pool + added_materials, [material])
        if added:
            added_materials.append(added[0])
            existing_keys.update(material_identity_keys(added[0]))
        else:
            pool = combined

    if added_materials:
        combined, added = append_unique_materials(pool, added_materials)
        save_material_pool(pool_path, combined)
        added_count = len(added)
    else:
        added_count = 0
    if added_metadata_candidates:
        combined_candidates, added_candidates = append_unique_materials(
            metadata_candidates,
            added_metadata_candidates,
        )
        save_material_pool(candidate_pool_path, combined_candidates)
        candidate_added_count = len(added_candidates)
    else:
        candidate_added_count = 0

    write_replenishment_log(
        output_dir,
        {
            "status": "success" if added_count else "no_material_added",
            "profile_url": profile_url,
            "profile_parse_status": profile_result.get("parse_status", ""),
            "candidate_count": len(profile_result.get("posts", [])),
            "attempted_count": attempted,
            "added_count": added_count,
            "candidate_added_count": candidate_added_count,
            "failed_candidates": failed_candidates,
            "created_at": utc_now(),
        },
    )
    return added_count


def load_profile_posts(profile_url: str, account: str, timeout: int) -> Dict[str, Any]:
    html_text, status, final_url, raw_path = load_or_fetch_html(
        url=profile_url,
        timeout=timeout,
        min_delay=0,
        max_delay=0,
        retries=0,
        use_cache=True,
    )
    return extract_profile_posts(
        html_text=html_text,
        profile_url=final_url,
        expected_account=account,
        http_status=status,
        raw_path=raw_path,
    )


def material_from_note(
    note: Dict[str, Any],
    post: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], str]:
    if note.get("parse_status") != "ok":
        return None, f"detail parse failed: {note.get('parse_status') or 'unknown'}"

    title = note.get("title") or post.get("title") or "每日文摘"
    paragraphs = rebuild_paragraphs(note.get("content", ""), "")
    if not paragraphs:
        return None, "detail had no paragraphs"

    note_url = note.get("note_url") or post.get("url") or ""
    note_id = post.get("note_id") or _note_id_from_url(note_url)
    return (
        {
            "id": f"xiaohongshu-{note_id or content_hash(title, paragraphs)[:12]}",
            "status": "candidate",
            "title": title,
            "paragraphs": paragraphs,
            "summary": build_summary(paragraphs),
            "source_name": note.get("account_name") or note.get("expected_account_name") or "",
            "source_url": note_url,
            "source_account_id": "xiaohongshu-xinxin",
            "content_hash": content_hash(title, paragraphs),
            "image_urls": normalize_image_urls(note.get("image_urls", [])),
            "note_id": note_id,
            "cover_url": post.get("cover_url", ""),
            "created_at": utc_now(),
        },
        "",
    )


def metadata_candidate_from_post(post: Dict[str, Any], profile_url: str) -> Dict[str, Any]:
    title = post.get("title") or "未命名候选"
    cover_url = normalize_image_urls([post.get("cover_url", "")])
    identity = post.get("note_id") or post.get("url") or post.get("cover_url") or title
    return {
        "id": f"xiaohongshu-metadata-{content_hash(title, [identity])[:12]}",
        "status": "candidate_metadata",
        "title": title,
        "note_id": post.get("note_id", ""),
        "source_url": post.get("url", ""),
        "profile_url": profile_url,
        "cover_url": cover_url[0] if cover_url else "",
        "created_at": utc_now(),
    }


def write_replenishment_log(output_dir: Path, item: Dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "material_replenishment_logs.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{path} must contain a JSON list")
    else:
        data = []
    data.append(item)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _post_seen(post: Dict[str, Any], existing_keys: Set[str]) -> bool:
    candidates = []
    for field in ("note_id", "url"):
        value = post.get(field)
        if isinstance(value, str) and value.strip():
            key_field = "source_url" if field == "url" else field
            candidates.append(f"{key_field}:{value.strip()}")
    return any(candidate in existing_keys for candidate in candidates)


def _failed_candidate(post: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "note_id": post.get("note_id", ""),
        "title": post.get("title", ""),
        "url": post.get("url", ""),
        "cover_url": post.get("cover_url", ""),
        "reason": reason,
    }


def _note_id_from_url(url: str) -> str:
    if "/explore/" not in url:
        return ""
    return url.split("/explore/", 1)[1].split("?", 1)[0].strip("/")


if __name__ == "__main__":
    raise SystemExit(main())
