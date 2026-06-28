from scripts.excerpt_pipeline.ocr import (
    FakeOcrClient,
    TencentOcrClient,
    create_ocr_client,
)


def test_fake_ocr_returns_empty_text_for_missing_images():
    client = FakeOcrClient()
    assert client.extract_texts([]) == []


def test_fake_ocr_returns_empty_by_default_even_with_images():
    client = FakeOcrClient()
    assert client.extract_texts(["a.jpg"]) == []


def test_fake_ocr_returns_seed_texts_up_to_image_count():
    client = FakeOcrClient(seed_texts=["第一行", "第二行"])

    assert client.extract_texts(["a.jpg"]) == ["第一行"]
    assert client.extract_texts(["a.jpg", "b.jpg", "c.jpg"]) == ["第一行", "第二行"]


def test_create_ocr_client_without_credentials_returns_fake(monkeypatch):
    for key in ["TENCENT_SECRET_ID", "TENCENT_SECRET_KEY"]:
        monkeypatch.delenv(key, raising=False)
    assert isinstance(create_ocr_client(), FakeOcrClient)


def test_create_ocr_client_with_partial_credentials_returns_fake(monkeypatch):
    monkeypatch.setenv("TENCENT_SECRET_ID", "id")
    monkeypatch.delenv("TENCENT_SECRET_KEY", raising=False)

    assert isinstance(create_ocr_client(), FakeOcrClient)


def test_tencent_ocr_client_is_importable_without_sdk_credentials():
    assert TencentOcrClient.__name__ == "TencentOcrClient"
