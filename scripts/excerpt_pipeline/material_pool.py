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
    published_hashes: Optional[Set[str]] = None,
) -> Optional[Material]:
    seen_hashes = set(published_hashes or set())
    for material in materials:
        content_hash = material.get("content_hash")
        if not content_hash:
            continue
        if content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)
        if material.get("status") != "candidate":
            continue
        return material
    return None
