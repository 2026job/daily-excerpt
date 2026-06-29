import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


Material = Dict[str, Any]


def _is_usable_material(material: Material) -> bool:
    title = material.get("title")
    paragraphs = material.get("paragraphs")
    summary = material.get("summary")
    return (
        isinstance(title, str)
        and bool(title.strip())
        and isinstance(paragraphs, list)
        and any(isinstance(paragraph, str) and paragraph.strip() for paragraph in paragraphs)
        and isinstance(summary, str)
        and bool(summary.strip())
    )


def load_material_pool(path: Path) -> List[Material]:
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"material pool must be a list: {path}")

    return [item for item in data if isinstance(item, dict)]


def save_material_pool(path: Path, materials: List[Material]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(materials, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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


def select_fallback_material(
    materials: Iterable[Material],
    *,
    published_hashes: Optional[Set[str]] = None,
) -> Optional[Material]:
    seen_hashes = set(published_hashes or set())
    for material in materials:
        content_hash = material.get("content_hash")
        if not isinstance(content_hash, str) or not content_hash:
            continue
        if content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)
        if material.get("status") != "candidate":
            continue
        if not _is_usable_material(material):
            continue
        return material
    return None
