from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
import yaml
from bs4 import BeautifulSoup

from ontolens.cli import main
from ontolens.project import build_project, load_project
from test_content import ONTOLOGY


def fixture(tmp_path):
    (tmp_path / "ontology.ttl").write_text(ONTOLOGY, encoding="utf-8")
    config = {"name": "test-project", "output": "out", "defaults": {"quality_report": True},
              "ontologies": [{"id": "first", "input": "ontology.ttl"},
                             {"id": "second", "input": "ontology.ttl", "quality_report": False}],
              "portal": {"enabled": True, "title": "<Test> & portal"}}
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path, config


def test_portal_paths_assets_downloads_and_precedence(tmp_path, monkeypatch):
    path, _ = fixture(tmp_path)
    monkeypatch.chdir(tmp_path.parent)
    project = load_project(path)
    assert project.output == tmp_path / "out"
    result = build_project(project)
    soup = BeautifulSoup(result.portal.read_text(encoding="utf-8"), "html.parser")
    assert soup.h1.get_text() == "<Test> & portal"
    assert len(soup.select("article")) == 2
    for link in soup.select("h2 a"):
        assert (result.directory / link["href"]).is_file()
    for index, page in enumerate(result.pages):
        doc = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        assert not doc.select('script[src]')
        assert not (page.parent / 'assets').exists()
        assert bool(doc.select_one("#quality-report")) == (index == 0)
        assert (page.parent / doc.select_one('nav[aria-label="Portal"] a')["href"]).resolve() == result.portal
        assert (page.parent / "downloads/ontology.ttl").read_text(encoding="utf-8") == ONTOLOGY
        assert doc.select_one('a[href="downloads/ontology.ttl"]')
        for link in doc.select('a[href], img[src]'):
            href = link.get("href", link.get("src"))
            parsed = urlsplit(href)
            if not parsed.scheme and not parsed.netloc and parsed.path:
                target = (page.parent / unquote(parsed.path)).resolve()
                assert target.is_relative_to(result.directory)
                assert target.exists()


def test_single_selection_cli_overrides_and_no_portal(tmp_path):
    path, _ = fixture(tmp_path)
    assert main(["build", str(path), "--ontology", "first", "--no-quality-report", "--no-portal"]) == 0
    assert not list((tmp_path / "out").rglob("index.html"))
    pages = list((tmp_path / "out").rglob("first.html"))
    assert len(pages) == 1
    assert not BeautifulSoup(pages[0].read_text(encoding="utf-8"), "html.parser").select_one("#quality-report")


@pytest.mark.parametrize("change,match", [
    ({"defaults": {"quality_report": "false"}}, "true or false"),
    ({"defaults": {"typo": True}}, "Unknown fields"),
    ({"ontologies": [{"id": "../bad", "input": "ontology.ttl"}]}, "Invalid ontology"),
    ({"ontologies": [{"id": "A", "input": "ontology.ttl"}, {"id": "a", "input": "ontology.ttl"}]}, "Duplicate"),
])
def test_invalid_config(tmp_path, change, match):
    path, config = fixture(tmp_path)
    config.update(change)
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        load_project(path)


def test_invalid_selection_or_content_checks_do_not_start_build(tmp_path):
    path, _ = fixture(tmp_path)
    project = load_project(path)
    with pytest.raises(ValueError, match="Unknown ontology"):
        build_project(project, ["absent"])
    with pytest.raises(ValueError, match="requires content"):
        build_project(project, overrides={"check_content": True})
    assert not project.output.exists()
