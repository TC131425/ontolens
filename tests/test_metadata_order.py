from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from ontolens.parser import ONTOLOGY_METADATA, load_ontology
from ontolens.render import generate


ORDER = [
    "Title", "Label", "Description", "Abstract", "Namespace URI", "Prefix",
    "Version info", "Version IRI", "Status", "Previous version",
    "Backward compatibility", "Incompatibility", "History note",
    "Creation date", "Issued date", "Modification Date", "License", "Citation",
    "DOI", "Publisher", "Source", "Imports", "See also", "Code repository",
    "Logo", "Diagram",
]


@pytest.mark.parametrize("recommendations", [False, True])
def test_metadata_order_is_stable_and_language_values_are_preserved(tmp_path: Path, recommendations: bool):
    graph = Graph()
    ontology = URIRef("https://example.org/ontology")
    graph.add((ontology, RDF.type, OWL.Ontology))
    for predicate, label in reversed(ONTOLOGY_METADATA):
        graph.add((ontology, predicate, Literal(label, lang="en")))
    graph.add((ontology, RDFS.label, Literal("Beispiel", lang="de")))
    source = tmp_path / "ontology.ttl"
    graph.serialize(source, format="turtle")

    doc = load_ontology(source, language="de", recommendations=recommendations)

    assert [item.label for item in doc.metadata] == ORDER
    assert not any(item.status for item in doc.metadata)
    labels = next(item for item in doc.metadata if item.label == "Label")
    assert [value.lang for value in labels.values] == ["de", "en"]


@pytest.mark.parametrize("combined", [False, True])
@pytest.mark.parametrize("recommendations", [False, True])
def test_missing_metadata_uses_the_same_positions_in_html(tmp_path: Path, combined: bool, recommendations: bool):
    source = tmp_path / "ontology.ttl"
    source.write_text('''@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
<https://example.org/ontology> a owl:Ontology ;
    dcterms:license <https://example.org/license> ;
    owl:versionInfo "1.0" ;
    rdfs:label "Example" ;
    dcterms:description "Example description" .
''', encoding="utf-8")
    content = tmp_path / "content.md"
    content.write_text("# Introduction\n\nExample.\n\n<!-- ontolens:metadata -->", encoding="utf-8")

    output = generate(source, tmp_path / "index.html", recommendations=recommendations,
                      content_path=content if combined else None)
    soup = BeautifulSoup(output.read_text(encoding="utf-8"), "html.parser")
    rows = soup.select("#metadata > table > tr, #metadata > table > tbody > tr")
    labels = [row.th.get_text(strip=True) for row in rows]
    assert labels[0] == "URI"
    assert labels[1:] == [label for label in ORDER if label in labels]
    assert ("Title" in labels) == recommendations
    assert ("Citation" in labels) == recommendations
    if recommendations:
        title = next(row for row in rows if row.th.get_text(strip=True) == "Title")
        assert "missing-mandatory" in title["class"]
        assert labels.index("Title") < labels.index("Label") < labels.index("Description")
        assert labels.index("Version IRI") < labels.index("License") < labels.index("Citation")
    else:
        assert labels == ["URI", "Label", "Description", "Version info", "License"]
