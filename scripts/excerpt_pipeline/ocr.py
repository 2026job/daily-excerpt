import base64
import os
import urllib.request
from dataclasses import dataclass
from typing import Iterable, List, Optional, Protocol


class OcrClient(Protocol):
    def extract_texts(self, image_urls: Iterable[str]) -> List[str]:
        ...


@dataclass
class FakeOcrClient:
    seed_texts: Optional[List[str]] = None

    def extract_texts(self, image_urls: Iterable[str]) -> List[str]:
        urls = list(image_urls)
        if self.seed_texts is None:
            return []
        return self.seed_texts[: len(urls)]


class TencentOcrClient:
    def __init__(self, secret_id: str, secret_key: str, region: str = "ap-guangzhou") -> None:
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile
        from tencentcloud.ocr.v20181119 import ocr_client

        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "ocr.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        self._client = ocr_client.OcrClient(cred, region, client_profile)

    def extract_texts(self, image_urls: Iterable[str]) -> List[str]:
        from tencentcloud.ocr.v20181119 import models

        results: List[str] = []
        for image_url in image_urls:
            request = models.GeneralBasicOCRRequest()
            if image_url.startswith(("http://", "https://")):
                request.ImageUrl = image_url
            else:
                with urllib.request.urlopen(image_url, timeout=20) as response:
                    request.ImageBase64 = base64.b64encode(response.read()).decode("ascii")
            response = self._client.GeneralBasicOCR(request)
            words = [item.DetectedText for item in response.TextDetections]
            results.append("\n".join(words))
        return results


def create_ocr_client() -> OcrClient:
    secret_id = os.getenv("TENCENT_SECRET_ID", "")
    secret_key = os.getenv("TENCENT_SECRET_KEY", "")
    region = os.getenv("TENCENT_OCR_REGION", "ap-guangzhou")
    if not secret_id or not secret_key:
        return FakeOcrClient()
    return TencentOcrClient(secret_id, secret_key, region)
