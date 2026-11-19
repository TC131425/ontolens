from ontolens.parser import load_ontology
from ontolens.render import _visualization_data
from test_content import ONTOLOGY


def test_union_domains_ranges_and_placeholders(tmp_path):
    source = tmp_path / 'union.ttl'
    source.write_text(ONTOLOGY + '''
ex:Other a owl:Class .
ex:unionProperty a owl:ObjectProperty ;
    rdfs:domain [ owl:unionOf (ex:Thing [ owl:unionOf (ex:Other ex:Thing) ]) ] ;
    rdfs:range [ owl:unionOf (ex:Other <https://external.example/Class>) ] .
ex:missingRange a owl:ObjectProperty ;
    rdfs:domain [ owl:unionOf (ex:Thing ex:Other) ] .
ex:missingDomain a owl:ObjectProperty ;
    rdfs:range [ owl:unionOf (ex:Thing ex:Other) ] .
ex:data a owl:DatatypeProperty ;
    rdfs:domain [ owl:unionOf (ex:Thing ex:Other ex:Thing) ] ;
    rdfs:range [ a rdfs:Datatype ; owl:unionOf (
        <http://www.w3.org/2001/XMLSchema#string> rdf:langString) ] .
ex:intersection a owl:ObjectProperty ;
    rdfs:domain [ owl:intersectionOf (ex:Thing ex:Other) ] ; rdfs:range ex:Thing .
''', encoding='utf-8')
    doc = load_ontology(source, quality_report=True)
    term = next(t for t in doc.object_properties if t.uri.endswith('#unionProperty'))
    assert term.domains[0].text.startswith('unionOf (')
    assert term.domains[0].union_members
    graph = _visualization_data(doc, True)['elements']
    edges = [e['data'] for e in graph['edges']]
    uri = 'https://example.org/ontology#'
    union_edges = [e for e in edges if e.get('href') == '#unionProperty']
    assert {(e['source'], e['target']) for e in union_edges} == {
        (uri + domain, target)
        for domain in ('Thing', 'Other')
        for target in (uri + 'Other', 'https://external.example/Class')
    }
    assert len(union_edges) == 4
    for name in ('missingRange', 'missingDomain'):
        assert sum(e.get('href') == '#' + name for e in edges) == 2
    assert not any(e.get('href') == '#intersection' for e in edges)
    data_edges = [e for e in edges if e['edgeKind'] == 'datatype-property']
    assert len(data_edges) == 2
    assert all(len(e['properties']) == 1 for e in data_edges)
    literals = [n['data'] for n in graph['nodes'] if n['data']['kind'] == 'literal']
    assert len(literals) == 1
    assert literals[0]['label'].startswith('unionOf (')
    assert not any('unionProperty' in issue.message for section in doc.quality.sections
                   for issue in section.issues if 'domain' in issue.message or 'range' in issue.message)


def test_cyclic_union_expression_does_not_recurse_forever(tmp_path):
    source = tmp_path / 'cycle.ttl'
    source.write_text(ONTOLOGY + '''
ex:cycle a owl:ObjectProperty ; rdfs:domain _:cycle ; rdfs:range ex:Thing .
_:cycle owl:unionOf (ex:Thing _:cycle) .
''', encoding='utf-8')
    graph = _visualization_data(load_ontology(source))['elements']
    assert any(e['data'].get('href') == '#cycle' for e in graph['edges'])
