from scripts.excerpt_pipeline.cleaning import (
    build_summary,
    clean_text,
    content_hash,
    rebuild_paragraphs,
    split_sentences,
)


def test_clean_text_removes_html_and_extra_space():
    raw = "  <p>生活是自己的</p>\n\n\n  #阅读  小红书  "
    assert clean_text(raw) == "生活是自己的\n#阅读 小红书"


def test_clean_text_unescapes_html_entities():
    assert clean_text("生活&amp;阅读&nbsp;&nbsp;继续") == "生活&阅读 继续"


def test_clean_text_normalizes_crlf_line_endings():
    raw = "第一行\r\n\r\n第二行\r第三行"
    assert clean_text(raw) == "第一行\n第二行\n第三行"


def test_clean_text_removes_known_platform_noise():
    raw = "生活是自己的\n3 亿人的生活经验，都在小红书\n慢慢来"
    assert clean_text(raw) == "生活是自己的\n慢慢来"


def test_split_sentences_handles_chinese_punctuation():
    text = "生活是自己的。不要活在别人的眼里！慢慢来，也是在抵达"
    assert split_sentences(text) == [
        "生活是自己的。",
        "不要活在别人的眼里！",
        "慢慢来，也是在抵达",
    ]


def test_split_sentences_handles_english_period():
    text = "Keep going. Stay curious. 慢慢来"
    assert split_sentences(text) == [
        "Keep going.",
        "Stay curious.",
        "慢慢来",
    ]


def test_split_sentences_handles_newlines():
    text = "第一句\n第二句。\n第三句"
    assert split_sentences(text) == [
        "第一句",
        "第二句。",
        "第三句",
    ]


def test_rebuild_paragraphs_uses_ocr_line_breaks_as_hints():
    html_text = "生活是自己的。不要活在别人的眼里。有人三分钟泡面，有人三小时煲汤。每一步都值得被肯定。"
    ocr_text = "生活是自己的。\n不要活在别人的眼里。\n\n有人三分钟泡面，有人三小时煲汤。\n每一步都值得被肯定。"

    assert rebuild_paragraphs(html_text, ocr_text, min_paragraph_len=12, max_paragraph_len=36) == [
        "生活是自己的。不要活在别人的眼里。",
        "有人三分钟泡面，有人三小时煲汤。每一步都值得被肯定。",
    ]


def test_rebuild_paragraphs_without_ocr_splits_long_text():
    text = "生活是自己的。不要活在别人的眼里。每个人都有自己的节奏。慢慢走，也是在认真抵达。"
    assert rebuild_paragraphs(text, "", min_paragraph_len=12, max_paragraph_len=32) == [
        "生活是自己的。不要活在别人的眼里。",
        "每个人都有自己的节奏。慢慢走，也是在认真抵达。",
    ]


def test_rebuild_paragraphs_merges_short_paragraphs():
    text = "短句。下一句很短。这里是一段足够长的内容。"
    assert rebuild_paragraphs(text, "", min_paragraph_len=8, max_paragraph_len=8) == [
        "短句。下一句很短。",
        "这里是一段足够长的内容。",
    ]


def test_build_summary_limits_length():
    paragraphs = ["生活是自己的。不要活在别人的眼里。", "慢慢来，也是在认真抵达。"]
    assert build_summary(paragraphs, limit=18) == "生活是自己的。不要活在别人..."


def test_content_hash_is_stable_for_same_content():
    first = content_hash("标题", ["第一段", "第二段"])
    second = content_hash("标题", ["第一段", "第二段"])
    assert first == second
    assert len(first) == 16
