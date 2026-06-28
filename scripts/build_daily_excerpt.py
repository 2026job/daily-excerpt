#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from excerpt_pipeline.cleaning import build_summary, content_hash, rebuild_paragraphs
from excerpt_pipeline.material_pool import load_material_pool, select_fallback_material
from excerpt_pipeline.models import make_excerpt, make_job_log
from excerpt_pipeline.ocr import create_ocr_client
from excerpt_pipeline.publishers import LocalJsonPublisher
from fetch_xiaohongshu_note import extract_note


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
    args = parser.parse_args()

    if not args.dry_run:
        raise SystemExit("only --dry-run publishing is supported")

    publisher = LocalJsonPublisher(Path(args.output_dir))
    published_hashes = _load_published_hashes(Path(args.output_dir) / "excerpts.json")
    material_pool = load_material_pool(Path(args.material_pool))

    try:
        raw_path = Path(args.raw_note_html) if args.raw_note_html else None
        excerpt = _build_from_raw_note(args.date, raw_path) if raw_path else None
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


def _build_from_raw_note(date: str, raw_note_html: Path) -> Optional[Dict[str, Any]]:
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
