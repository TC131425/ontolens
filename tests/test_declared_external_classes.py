from bs4 import BeautifulSoup
import pytest

from ontolens.parser import load_ontology
from ontolens.render import _visualization_data, generate
from test_external_datatype_domains import PREFIXES


@pytest.mark.parametrize('format,suffix', [('turtle', '.ttl'), ('xml', '.rdf'), ('nt', '.nt'), ('json-ld', '.jsonld')])
def test_all_declared_named_classes_are_included_without_changing_local_catalog(tmp_path, format, suffix):
    from rdflib import Graph

    text = PREFIXES + '''
ex:Local a owl:Class ; rdfs:subClassOf ext:Parent .
ext:Isolated a owl:Class, rdfs:Class ; rdfs:label "Isolated class"@en, "Einzelne Klasse"@de .
ext:Parent a owl:Class .
ext:Child a rdfs:Class ; rdfs:subClassOf ext:Parent ; owl:equivalentClass ext:Other .
ext:Other a owl:Class ; owl:equivalentClass ext:Child .
<https://schema.org/Person> a owl:Class .
ext:UnrelatedIndividual a owl:NamedIndividual .
ext:UnrelatedProperty a owl:ObjectProperty .
[] a owl:Class .
'''
    source = tmp_path / ('classes' + suffix)
    Graph().parse(data=text, format='turtle').serialize(source, format=format)
    doc = load_ontology(source, language='de', quality_report=True)
    assert [c.uri for c in doc.classes] == ['https://example.org/ontology#Local']
    assert doc.term_count == 1
    assert len(doc.external_classes) == 5
    assert all(not issue.message.startswith('ext:') for section in doc.quality.sections for issue in section.issues)
    graph = _visualization_data(doc, include_external_classes=True)
    nodes = {node['data']['id']: node['data'] for node in graph['elements']['nodes']}
    assert len(nodes) == 6
    assert nodes['https://external.example/Isolated']['label'] == 'Einzelne Klasse'
    assert nodes['https://schema.org/Person']['kind'] == 'external-class'
    for term in doc.external_classes:
        assert nodes[term.uri]['href'] == term.uri
        assert nodes[term.uri]['kind'] == 'external-class'
    edges = [edge['data'] for edge in graph['elements']['edges']]
    assert len(edges) == 4  # Two subclass edges and the equivalence's parallel pair.
    assert {(edge['source'], edge['target']) for edge in edges if edge['edgeKind'] == 'subClassOf'} == {
        ('https://example.org/ontology#Local', 'https://external.example/Parent'),
        ('https://external.example/Child', 'https://external.example/Parent'),
    }
    assert not any('Isolated' in edge['source'] or 'Isolated' in edge['target'] for edge in edges)
    assert {'https://schema.org/', 'https://external.example/'} <= {item['uri'] for item in graph['ontologies']}


def test_external_only_ontology_keeps_graph_in_combined_documentation(tmp_path):
    source = tmp_path / 'external.ttl'
    source.write_text(PREFIXES + 'ext:Isolated a rdfs:Class .', encoding='utf-8')
    content = tmp_path / 'content.md'
    content.write_text('# Introduction\n\nAn external class without relationships.', encoding='utf-8')
    doc = load_ontology(source)
    assert not doc.classes
    assert _visualization_data(doc)['counts'] == {'nodes': 0, 'edges': 0}
    assert _visualization_data(doc, include_external_classes=True)['counts'] == {'nodes': 1, 'edges': 0}
    output = generate(source, tmp_path / 'combined.html', content_path=content, include_external_classes=True)
    soup = BeautifulSoup(output.read_text(encoding='utf-8'), 'html.parser')
    assert soup.select_one('#visualization #ontology-graph')
    assert soup.select_one('a[href="#visualization"]')
    assert not soup.select_one('#classes')
