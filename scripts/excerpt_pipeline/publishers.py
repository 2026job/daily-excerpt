import json
from pathlib import Path
from typing import Any, Dict, Protocol


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
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} contains invalid JSON") from exc
            if not isinstance(data, list):
                raise ValueError(f"{path} must contain a JSON list")
        else:
            data = []
        item_copy = dict(item)
        item_id = item_copy.get("_id") or f"local-{len(data) + 1}"
        item_copy["_id"] = item_id
        data.append(item_copy)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return item_id
