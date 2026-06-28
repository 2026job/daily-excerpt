import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Protocol
import urllib.parse
import urllib.request


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


class WeChatCloudPublisher:
    def __init__(
        self,
        *,
        env_id: Optional[str] = None,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> None:
        self.env_id = env_id if env_id is not None else os.getenv("WECHAT_CLOUD_ENV_ID", "")
        self.app_id = app_id if app_id is not None else os.getenv("WECHAT_APP_ID", "")
        self.app_secret = app_secret if app_secret is not None else os.getenv("WECHAT_APP_SECRET", "")
        self.access_token = access_token if access_token is not None else os.getenv("WECHAT_ACCESS_TOKEN", "")

        missing = []
        if not self.env_id:
            missing.append("WECHAT_CLOUD_ENV_ID")
        if not self.app_id:
            missing.append("WECHAT_APP_ID")
        if not self.app_secret:
            missing.append("WECHAT_APP_SECRET")
        if missing:
            raise ValueError(f"missing WeChat credentials: {', '.join(missing)}")

    def publish_excerpt(self, excerpt: Dict[str, Any]) -> str:
        return self._database_add("excerpts", excerpt)

    def publish_job_log(self, log: Dict[str, Any]) -> str:
        return self._database_add("job_logs", log)

    def build_add_payload(self, collection: str, data: Dict[str, Any]) -> Dict[str, str]:
        document = json.dumps({"data": data}, ensure_ascii=False, separators=(",", ":"))
        return {
            "env": self.env_id,
            "query": f'db.collection("{collection}").add({document})',
        }

    def _database_add(self, collection: str, data: Dict[str, Any]) -> str:
        token = self.access_token or self._get_access_token()
        payload = json.dumps(self.build_add_payload(collection, data), ensure_ascii=False).encode("utf-8")
        url = "https://api.weixin.qq.com/tcb/databaseadd?" + urllib.parse.urlencode({"access_token": token})
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        if body.get("errcode", 0) != 0:
            raise RuntimeError(f"WeChat databaseadd failed: {body}")
        return body.get("id_list", [""])[0]

    def _get_access_token(self) -> str:
        query = urllib.parse.urlencode(
            {
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            }
        )
        with urllib.request.urlopen(f"https://api.weixin.qq.com/cgi-bin/token?{query}", timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        token = body.get("access_token")
        if not token:
            raise RuntimeError(f"WeChat token request failed: {body}")
        return token
