from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from ontolens.assets import AssetBundle
from ontolens.render import generate


ONTOLOGY = """\
@prefix ex: <https://example.org/ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix vann: <http://purl.org/vocab/vann/> .

<https://example.org/ontology> a owl:Ontology ;
    rdfs:label "Example ontology"@en ;
    vann:preferredNamespacePrefix "ex" ;
    vann:preferredNamespaceUri "https://example.org/ontology#" .

ex:Thing a owl:Class ;
    rdfs:label "Thing"@en .

ex:relatedTo a owl:ObjectProperty ;
    rdfs:label "related to"@en ;
    rdfs:domain ex:Thing ;
    rdfs:range ex:Thing .

ex:code a owl:AnnotationProperty, rdf:Property ;
    rdfs:label "code"@en .
"""


CONTENT = """\
---
language: de
title: Combined example
description: Narrative and technical documentation.
---

<!-- ontolens:metadata -->

# Introduction

Read about [[ex:Thing|the central class]].

![Model](figure.svg)

<!-- ontolens:visualization -->

## Usage

The generated reference follows below.

<!-- ontolens:cross-reference -->
"""


def _write_fixture(tmp_path: Path, content: str = CONTENT) -> tuple[Path, Path, Path]:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "dist"
    source_dir.mkdir()
    output_dir.mkdir()
    ontology = source_dir / "ontology.ttl"
    markdown = source_dir / "documentation.md"
    ontology.write_text(ONTOLOGY, encoding="utf-8")
    markdown.write_text(content, encoding="utf-8")
    (source_dir / "figure.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
    return ontology, markdown, output_dir / "index.html"


def test_generates_combined_documentation(tmp_path: Path) -> None:
    ontology, markdown, output = _write_fixture(tmp_path)

    actual_output = generate(
        ontology,
        output,
        content_path=markdown,
        generated_at=datetime(2026, 8, 26, 14, 30, 5),
    )

    assert actual_output == output.parent / "2026-08-26T14-30-05_index" / "index.html"
    soup = BeautifulSoup(actual_output.read_text(encoding="utf-8"), "html.parser")
    assert soup.html["lang"] == "de"
    assert soup.title.string == "Combined example"
    assert soup.select_one("main.editorial-flow") is not None
    assert soup.select_one('main p a[href="#Thing"]').get_text(strip=True) == "the central class"
    assert soup.select_one("main > p > img")["src"] == "img/figure.svg"
    assert (actual_output.parent / "img" / "figure.svg").is_file()
    assert soup.select_one("#metadata") is not None
    assert soup.select_one("#visualization") is not None
    assert soup.select_one("#cross-reference") is not None
    assert soup.select_one(".toc-title").get_text(strip=True) == "Inhaltsverzeichnis"

    groups = soup.select(".toc-reference-groups details")
    assert [group.select_one("summary span").get_text(strip=True) for group in groups] == [
        "Klassen",
        "Objekt-Properties",
        "Annotations-Properties",
        "RDF-Properties",
    ]
    assert groups[0].has_attr("open")
    assert not groups[1].has_attr("open")

    ids = [element["id"] for element in soup.select("[id]")]
    assert len(ids) == len(set(ids))
    assert soup.select_one("#code") is not None
    assert soup.select_one("#code-rdf-property") is not None


def test_defaults_missing_slots_around_markdown(tmp_path: Path) -> None:
    ontology, markdown, output = _write_fixture(tmp_path, "# Introduction\n\nText")

    actual_output = generate(ontology, output, content_path=markdown)

    soup = BeautifulSoup(actual_output.read_text(encoding="utf-8"), "html.parser")
    direct_ids = [child.get("id") for child in soup.main.children if getattr(child, "name", None)]
    assert direct_ids[0] == "metadata"
    assert "overview" in direct_ids
    assert direct_ids[-1] == "cross-reference"


def test_explicit_markdown_links_survive_combined_html(tmp_path: Path) -> None:
    ontology, markdown, output = _write_fixture(tmp_path, """# Links

Read [Example](https://example.org/docs) and [A \\[link\\]](<https://example.org/a(b)?x=1&y=2>).

[Reference](<#cross-reference>) and [Contact](<mailto:person@example.org>).

<https://example.org/automatic>

Bare address: https://example.org/plain
""")
    actual_output = generate(ontology, output, content_path=markdown)
    soup = BeautifulSoup(actual_output.read_text(encoding="utf-8"), "html.parser")
    for href, label in (
        ("https://example.org/docs", "Example"),
        ("https://example.org/a(b)?x=1&y=2", "A [link]"),
        ("#cross-reference", "Reference"),
        ("mailto:person@example.org", "Contact"),
        ("https://example.org/automatic", "https://example.org/automatic"),
    ):
        assert soup.main.find("a", href=href).get_text() == label
    assert soup.find("a", href="https://example.org/plain") is None


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("# Text\n\n[[ex:Missing]]", "unknown ontology term 'ex:Missing'"),
        ("<!-- ontolens:not-a-section -->", "Unknown OntoLens slot 'not-a-section'"),
    ],
)
def test_reports_invalid_content(tmp_path: Path, content: str, message: str) -> None:
    ontology, markdown, output = _write_fixture(tmp_path, content)

    with pytest.raises(ValueError, match=message):
        generate(ontology, output, content_path=markdown)


def test_standard_documentation_stays_available(tmp_path: Path) -> None:
    ontology, _, output = _write_fixture(tmp_path)

    actual_output = generate(ontology, output)

    assert actual_output.parent.name.endswith("_index")
    assert (actual_output.parent / "img").is_dir()
    soup = BeautifulSoup(actual_output.read_text(encoding="utf-8"), "html.parser")
    assert soup.select_one("main.editorial-flow") is None
    assert soup.select_one("#cross-reference") is not None


def test_asset_bundle_disambiguates_equal_filenames(tmp_path: Path) -> None:
    first = tmp_path / "first" / "figure.svg"
    second = tmp_path / "second" / "figure.svg"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text('<svg xmlns="http://www.w3.org/2000/svg"><title>first</title></svg>', encoding="utf-8")
    second.write_text('<svg xmlns="http://www.w3.org/2000/svg"><title>second</title></svg>', encoding="utf-8")
    assets = AssetBundle(tmp_path / "output")

    assert assets.copy_image(first) == "img/figure.svg"
    assert assets.copy_image(first) == "img/figure.svg"
    assert assets.copy_image(second) == "img/figure-2.svg"
    assert (tmp_path / "output" / "img" / "figure.svg").read_bytes() == first.read_bytes()
    assert (tmp_path / "output" / "img" / "figure-2.svg").read_bytes() == second.read_bytes()
