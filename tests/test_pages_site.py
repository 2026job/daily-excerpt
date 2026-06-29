from pathlib import Path


def test_pages_site_has_static_reader():
    html = Path("site/index.html").read_text(encoding="utf-8")

    assert "data/excerpts.json" in html
    assert 'id="excerpt-title"' in html
    assert 'id="history-list"' in html
    assert "renderExcerpt" in html


def test_pages_seed_data_is_valid_empty_list():
    seed = Path("site/data/excerpts.json").read_text(encoding="utf-8")

    assert seed.strip() == "[]"


def test_workflow_deploys_github_pages_site():
    workflow = Path(".github/workflows/daily-excerpt.yml").read_text(encoding="utf-8")

    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "mkdir -p site/data" in workflow
    assert "cp data/output/excerpts.json site/data/excerpts.json" in workflow
    assert "actions/upload-pages-artifact@v3" in workflow
    assert "actions/deploy-pages@v4" in workflow
