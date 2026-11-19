from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from ontolens.cli import main
from ontolens.render import generate
from ontolens.scaffold import create_content
from test_content import _write_fixture


@pytest.mark.parametrize("language", ["de", "en"])
@pytest.mark.parametrize("profile", ["compact", "standard"])
def test_template_builds_with_optional_quality(tmp_path: Path, language: str, profile: str):
    ontology, _, output = _write_fixture(tmp_path)
    content = tmp_path / "template.md"
    assert main(["init-content", str(ontology), "-o", str(content),
                 "--language", language, "--profile", profile]) == 0
    source = content.read_text(encoding="utf-8")
    assert "Example ontology" in source
    assert ("chapter design-decisions" in source) == (profile == "standard")
    for quality in (False, True):
        result = generate(ontology, output, content_path=content, quality_report=quality)
        soup = BeautifulSoup(result.read_text(encoding="utf-8"), "html.parser")
        assert soup.select_one("h1#chapter-introduction")
        assert soup.select_one('aside a[href="#chapter-introduction"]')
        assert bool(soup.select_one("section#quality-report")) == quality
        assert soup.select_one(".toc-reference-groups")
        ids = [tag["id"] for tag in soup.select("[id]")]
        assert len(ids) == len(set(ids))


def test_existing_content_is_never_overwritten(tmp_path: Path):
    ontology, content, _ = _write_fixture(tmp_path)
    before = content.read_bytes()
    with pytest.raises(FileExistsError):
        create_content(ontology, content)
    assert content.read_bytes() == before


def test_default_output_and_legacy_cli(tmp_path: Path, monkeypatch):
    ontology, _, output = _write_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["init-content", str(ontology), "--language", "de"]) == 0
    templates = list((tmp_path / "build" / "ontology").glob("*_ontology-documentation.de/ontology-documentation.de.md"))
    assert len(templates) == 1
    assert not ontology.with_name("ontology-documentation.de.md").exists()
    assert main([str(ontology), "-o", str(output)]) == 0


def test_default_build_is_separate_from_sources(tmp_path: Path, monkeypatch):
    ontology, content, _ = _write_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main([str(ontology)]) == 0
    assert main([str(ontology), "--content", str(content)]) == 0
    builds = list((tmp_path / "build" / "ontology").glob("*/ontology.html"))
    assert builds
    assert all((build.parent / "img").is_dir() for build in builds)
    assert not list(ontology.parent.glob("*.html"))


@pytest.mark.parametrize("body,message", [
    ("<!-- ontolens:chapter intro -->\n# Eins\n\n<!-- ontolens:chapter intro -->\n# Zwei", "Duplicate"),
    ("<!-- ontolens:chapter intro -->\nText", "must precede"),
    ("<!-- ontolens:chapter BAD -->\n# Titel", "Invalid"),
])
def test_invalid_chapter_markers(tmp_path: Path, body: str, message: str):
    ontology, content, output = _write_fixture(tmp_path, body)
    with pytest.raises(ValueError, match=message):
        generate(ontology, output, content_path=content)


def test_markers_inside_code_are_not_interpreted(tmp_path: Path):
    body = '# Text\n\n```html\n<!-- ontolens:chapter example -->\n```'
    ontology, content, output = _write_fixture(tmp_path, body)
    result = generate(ontology, output, content_path=content)
    soup = BeautifulSoup(result.read_text(encoding="utf-8"), "html.parser")
    assert "ontolens:chapter example" in soup.select_one("pre").get_text()
