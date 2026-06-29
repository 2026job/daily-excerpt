from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_image_urls(image_urls: Optional[List[Any]]) -> List[str]:
    normalized = []
    for url in image_urls or []:
        if not isinstance(url, str):
            continue
        url = url.strip()
        if not url:
            continue
        if url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        normalized.append(url)
    return normalized


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
    image_urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "date": date,
        "title": title,
        "paragraphs": paragraphs,
        "image_urls": normalize_image_urls(image_urls),
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
