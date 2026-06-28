import json

import pytest

from scripts.excerpt_pipeline.publishers import LocalJsonPublisher, WeChatCloudPublisher


def test_wechat_publisher_requires_credentials():
    with pytest.raises(ValueError) as exc_info:
        WeChatCloudPublisher(env_id="", app_id="", app_secret="")

    message = str(exc_info.value)
    assert "WECHAT_CLOUD_ENV_ID" in message
    assert "WECHAT_APP_ID" in message
    assert "WECHAT_APP_SECRET" in message


def test_wechat_publisher_reads_credentials_from_environment(monkeypatch):
    monkeypatch.setenv("WECHAT_CLOUD_ENV_ID", "env-from-os")
    monkeypatch.setenv("WECHAT_APP_ID", "app-from-os")
    monkeypatch.setenv("WECHAT_APP_SECRET", "secret-from-os")

    publisher = WeChatCloudPublisher()

    assert publisher.env_id == "env-from-os"
    assert publisher.app_id == "app-from-os"
    assert publisher.app_secret == "secret-from-os"


def test_wechat_publisher_builds_database_payload():
    publisher = WeChatCloudPublisher(
        env_id="env",
        app_id="app",
        app_secret="secret",
        access_token="token",
    )

    payload = publisher.build_add_payload("excerpts", {"title": "每日文摘"})

    assert payload == {
        "env": "env",
        "query": 'db.collection("excerpts").add({"data":{"title":"每日文摘"}})',
    }


def test_wechat_publisher_routes_excerpt_and_job_log_to_expected_collections():
    calls = []

    class RecordingPublisher(WeChatCloudPublisher):
        def _database_add(self, collection, data):
            calls.append((collection, data))
            return "cloud-id"

    publisher = RecordingPublisher(
        env_id="env",
        app_id="app",
        app_secret="secret",
        access_token="token",
    )

    assert publisher.publish_excerpt({"title": "每日文摘"}) == "cloud-id"
    assert publisher.publish_job_log({"status": "success"}) == "cloud-id"
    assert calls == [
        ("excerpts", {"title": "每日文摘"}),
        ("job_logs", {"status": "success"}),
    ]


def test_local_json_publisher_still_appends_items(tmp_path):
    publisher = LocalJsonPublisher(tmp_path)

    first_id = publisher.publish_excerpt({"title": "one"})
    second_id = publisher.publish_excerpt({"title": "two"})

    assert first_id == "local-1"
    assert second_id == "local-2"
    assert json.loads((tmp_path / "excerpts.json").read_text(encoding="utf-8")) == [
        {"title": "one", "_id": "local-1"},
        {"title": "two", "_id": "local-2"},
    ]
