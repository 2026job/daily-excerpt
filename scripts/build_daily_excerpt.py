#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from excerpt_pipeline.cleaning import build_summary, content_hash, rebuild_paragraphs
from excerpt_pipeline.material_pool import load_material_pool, select_fallback_material
from excerpt_pipeline.models import make_excerpt, make_job_log
from excerpt_pipeline.ocr import create_ocr_client
from excerpt_pipeline.publishers import LocalJsonPublisher
from fetch_xiaohongshu_note import extract_note, fetch_html


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and publish the daily excerpt.")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "data" / "output"))
    parser.add_argument(
        "--material-pool",
        default=str(PROJECT_ROOT / "data" / "material_pool" / "seed.json"),
    )
    parser.add_argument("--raw-note-html", default="")
    parser.add_argument("--note-url", default="")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    if not args.dry_run:
        raise SystemExit("only --dry-run publishing is supported")

    publisher = LocalJsonPublisher(Path(args.output_dir))

    try:
        published_hashes = _load_published_hashes(Path(args.output_dir) / "excerpts.json")
        material_pool = load_material_pool(Path(args.material_pool))
        if args.note_url:
            excerpt, fresh_skip_reason = _build_from_note_url(args.date, args.note_url, args.timeout)
        else:
            raw_path = Path(args.raw_note_html) if args.raw_note_html else None
            excerpt, fresh_skip_reason = _build_from_raw_note(args.date, raw_path)
        if excerpt and excerpt["content_hash"] not in published_hashes:
            excerpt_id = publisher.publish_excerpt(excerpt)
            publisher.publish_job_log(
                make_job_log(
                    date=args.date,
                    status="success",
                    source_name=excerpt["source_name"],
                    excerpt_id=excerpt_id,
                    message="published fresh excerpt",
                )
            )
            print(f"published excerpt {excerpt_id}")
            return 0
        if excerpt and excerpt["content_hash"] in published_hashes:
            fresh_skip_reason = "fresh excerpt duplicate"

        fallback = select_fallback_material(material_pool, published_hashes=published_hashes)
        if not fallback:
            publisher.publish_job_log(
                make_job_log(
                    date=args.date,
                    status="failed",
                    source_name="",
                    message="no fresh content and no fallback material",
                )
            )
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
                message=_fallback_message(fresh_skip_reason),
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


def _build_from_raw_note(
    date: str, raw_note_html: Optional[Path]
) -> Tuple[Optional[Dict[str, Any]], str]:
    if raw_note_html is None:
        return None, "raw note html not provided"
    if not raw_note_html.exists():
        return None, "raw note html missing"
    html_text = raw_note_html.read_text(encoding="utf-8")
    note = extract_note(html_text, "local-fixture", "欣欣的阅读疗愈记")
    if note.get("parse_status") != "ok":
        return None, f"raw note parse failed: {note.get('parse_status') or 'unknown'}"

    ocr_texts = create_ocr_client().extract_texts(note.get("image_urls", []))
    paragraphs = rebuild_paragraphs(note.get("content", ""), "\n\n".join(ocr_texts))
    if not paragraphs:
        return None, "raw note had no paragraphs"

    title = note.get("title") or "每日文摘"
    return (
        make_excerpt(
            date=date,
            title=title,
            paragraphs=paragraphs,
            summary=build_summary(paragraphs),
            source_name=note.get("account_name") or note.get("expected_account_name") or "",
            source_url=note.get("note_url") or "",
            source_account_id="xiaohongshu-xinxin",
            content_hash=content_hash(title, paragraphs),
            publish_type="fresh",
        ),
        "",
    )


def _build_from_note_url(
    date: str, note_url: str, timeout: int
) -> Tuple[Optional[Dict[str, Any]], str]:
    html_text, _status = fetch_html(note_url, timeout)
    note = extract_note(html_text, note_url, "欣欣的阅读疗愈记")
    if note.get("parse_status") != "ok":
        return None, f"note url parse failed: {note.get('parse_status') or 'unknown'}"

    ocr_texts = create_ocr_client().extract_texts(note.get("image_urls", []))
    paragraphs = rebuild_paragraphs(note.get("content", ""), "\n\n".join(ocr_texts))
    if not paragraphs:
        return None, "note url had no paragraphs"

    title = note.get("title") or "每日文摘"
    return (
        make_excerpt(
            date=date,
            title=title,
            paragraphs=paragraphs,
            summary=build_summary(paragraphs),
            source_name=note.get("account_name") or note.get("expected_account_name") or "",
            source_url=note.get("note_url") or note_url,
            source_account_id="xiaohongshu-xinxin",
            content_hash=content_hash(title, paragraphs),
            publish_type="fresh",
        ),
        "",
    )


def _load_published_hashes(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} contains invalid JSON") from exc
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")
    hashes = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        content_hash_value = item.get("content_hash")
        if isinstance(content_hash_value, str):
            hashes.add(content_hash_value)
    return hashes


def _fallback_message(fresh_skip_reason: str) -> str:
    if fresh_skip_reason:
        return f"used fallback material: {fresh_skip_reason}"
    return "used fallback material"


if __name__ == "__main__":
    raise SystemExit(main())
