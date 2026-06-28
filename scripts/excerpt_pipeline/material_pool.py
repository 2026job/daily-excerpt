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
    published_hashes: Set[str] = set(),
) -> Optional[Material]:
    for material in materials:
        if material.get("status") != "candidate":
            continue
        if material.get("content_hash") in published_hashes:
            continue
        return material
    return None
