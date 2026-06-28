import hashlib
import html
import re
from typing import Iterable, List


NOISE_PATTERNS = [
    r"登录后推荐更懂你的笔记",
    r"3 亿人的生活经验，都在小红书",
]


def clean_text(value: str) -> str:
    if not value:
        return ""

    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\r\n?", "\n", text)
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, "", text)

    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t\xa0]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def split_sentences(text: str) -> List[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[。！？!?；;。\.])\s*|\n+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _clean_ocr_blocks(ocr_text: str) -> List[str]:
    text = html.unescape(ocr_text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\r\n?", "\n", text)
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, "", text)

    blocks = []
    for block in re.split(r"\n\s*\n+", text):
        lines = []
        for line in block.split("\n"):
            line = re.sub(r"[ \t]+", " ", line).strip()
            if line:
                lines.append(line)
        if lines:
            blocks.append("\n".join(lines))
    return blocks


def _ocr_paragraph_sentence_counts(ocr_text: str) -> List[int]:
    blocks = _clean_ocr_blocks(ocr_text)
    if len(blocks) < 2:
        return []

    counts = []
    for block in blocks:
        count = len(split_sentences(block))
        if count:
            counts.append(count)
    return counts


def _append_or_flush(paragraphs: List[str], current: List[str]) -> List[str]:
    if not current:
        return []
    paragraph = "".join(current).strip()
    if paragraph:
        paragraphs.append(paragraph)
    return []


def rebuild_paragraphs(
    html_text: str,
    ocr_text: str = "",
    *,
    min_paragraph_len: int = 24,
    max_paragraph_len: int = 80,
) -> List[str]:
    sentences = split_sentences(html_text)
    if not sentences:
        sentences = split_sentences(ocr_text)
    if not sentences:
        return []

    counts = _ocr_paragraph_sentence_counts(ocr_text)
    if counts and sum(counts) <= len(sentences):
        paragraphs = []
        index = 0
        for count in counts:
            chunk = sentences[index : index + count]
            if chunk:
                paragraphs.append("".join(chunk))
            index += count
        if index < len(sentences):
            paragraphs.append("".join(sentences[index:]))
        return _merge_short_paragraphs(paragraphs, min_paragraph_len)

    paragraphs: List[str] = []
    current: List[str] = []
    for index, sentence in enumerate(sentences):
        next_text = "".join(current) + sentence
        remaining = sentences[index + 1 :]
        remaining_text = "".join(remaining)
        if (
            current
            and len("".join(current)) >= min_paragraph_len
            and remaining_text
            and len(next_text + remaining_text) > max_paragraph_len
        ):
            current = _append_or_flush(paragraphs, current)
            next_text = sentence
        if current and len(next_text) > max_paragraph_len:
            current = _append_or_flush(paragraphs, current)
        current.append(sentence)
    _append_or_flush(paragraphs, current)
    return _merge_short_paragraphs(paragraphs, min_paragraph_len)


def _merge_short_paragraphs(paragraphs: Iterable[str], min_paragraph_len: int) -> List[str]:
    result: List[str] = []
    buffer = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if not buffer:
            buffer = paragraph
        elif len(buffer) < min_paragraph_len:
            buffer += paragraph
        else:
            result.append(buffer)
            buffer = paragraph
    if buffer:
        result.append(buffer)
    return result


def build_summary(paragraphs: List[str], limit: int = 48) -> str:
    text = clean_text("".join(paragraphs))
    if len(text) <= limit:
        return text
    cutoff = max(0, limit - 3)
    snippet = text[:cutoff].rstrip()
    for marker in ("的", "，", "。", "！", "？", "；", ",", ".", "!", "?", ";"):
        index = snippet.rfind(marker)
        if index > 0:
            snippet = snippet[:index] if marker == "的" else snippet[: index + 1]
            break
    return snippet.rstrip() + "..."


def content_hash(title: str, paragraphs: List[str]) -> str:
    payload = clean_text(title) + "\n" + "\n".join(clean_text(item) for item in paragraphs)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
