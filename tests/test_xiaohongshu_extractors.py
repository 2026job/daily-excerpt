from pathlib import Path

from scripts.fetch_xiaohongshu_note import extract_note
from scripts.fetch_xiaohongshu_user_posts import extract_profile_posts


FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_note_from_fixture():
    html_text = (FIXTURES / "xiaohongshu-note.html").read_text(encoding="utf-8")
    note = extract_note(
        html_text,
        "https://www.xiaohongshu.com/explore/example",
        "欣欣的阅读疗愈记",
    )
    assert note["parse_status"] == "ok"
    assert note["title"]
    assert note["content"]
    assert note["material_notes"]["phrase_candidates"]


def test_extract_profile_posts_accepts_raw_path(tmp_path):
    html_text = (Path("data/raw/xiaohongshu-user-profile.html")).read_text(encoding="utf-8")
    raw_path = Path.cwd() / "data/raw/xiaohongshu-user-profile.html"
    result = extract_profile_posts(
        html_text=html_text,
        profile_url="https://www.xiaohongshu.com/user/profile/5c1db0ab0000000005013197",
        expected_account="欣欣的阅读疗愈记",
        http_status=200,
        raw_path=raw_path,
    )
    assert result["parse_status"] == "ok"
    assert result["profile"]["nickname"] == "欣欣的阅读疗愈记"
    assert len(result["posts"]) >= 1
