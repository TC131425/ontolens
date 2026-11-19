from ontolens.parser import load_ontology
from ontolens.render import _visualization_data, render_html


PREFIXES = '''
@prefix ex: <https://example.org/ontology#> .
@prefix ext: <https://external.example/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<https://example.org/ontology> a owl:Ontology .
'''


def test_external_datatype_domains_without_local_classes(tmp_path):
    source = tmp_path / 'external.ttl'
    source.write_text(PREFIXES + '''
ext:Element a owl:Class ; rdfs:label "Element" .
ex:name a owl:DatatypeProperty ; rdfs:domain ext:Element ; rdfs:range xsd:string .
ex:code a owl:DatatypeProperty ; rdfs:domain ext:Element ; rdfs:range xsd:string .
ex:weight a owl:DatatypeProperty ; rdfs:domain ext:Element ; rdfs:range xsd:decimal .
ex:unknownRange a owl:DatatypeProperty ; rdfs:domain ext:Undeclared .
ex:noDomain a owl:DatatypeProperty ; rdfs:range xsd:string .
''', encoding='utf-8')
    doc = load_ontology(source, quality_report=True)
    quality = doc.quality
    assert not doc.classes
    graph = _visualization_data(doc)
    nodes = {n['data']['id']: n['data'] for n in graph['elements']['nodes']}
    edges = [e['data'] for e in graph['elements']['edges']]
    assert graph['counts'] == {'nodes': 5, 'edges': 3}
    for name in ('Element', 'Undeclared'):
        node = nodes['https://external.example/' + name]
        assert node['kind'] == 'external-class'
        assert node['href'] == node['id']
        assert node['ontology'] == 'https://external.example/'
    assert nodes['https://external.example/Element']['label'] == 'Element'
    string = next(e for e in edges if e['target'].endswith('#string'))
    assert {p['href'] for p in string['properties']} == {'#name', '#code'}
    assert any(e['source'].endswith('/Undeclared') and e['target'] == 'literal:Literal' for e in edges)
    assert all(p['href'] != '#noDomain' for e in edges for p in e['properties'])
    assert _visualization_data(doc, True) == graph
    assert doc.quality == quality
    assert 'id="ontology-graph"' in render_html(doc)


def test_mixed_union_domains_reuse_external_object_property_nodes(tmp_path):
    source = tmp_path / 'union.ttl'
    source.write_text(PREFIXES + '''
ex:Local a owl:Class .
ex:related a owl:ObjectProperty ; rdfs:domain ex:Local ; rdfs:range ext:Element .
ex:code a owl:DatatypeProperty ;
  rdfs:domain [ owl:unionOf (ex:Local ext:Element [ owl:unionOf (ext:Element ext:Other) ]) ] ;
  rdfs:range xsd:string .
ex:intersection a owl:DatatypeProperty ;
  rdfs:domain [ owl:intersectionOf (ex:Local ext:Element) ] ; rdfs:range xsd:string .
''', encoding='utf-8')
    graph = _visualization_data(load_ontology(source))['elements']
    nodes = [n['data'] for n in graph['nodes']]
    assert len(nodes) == len({n['id'] for n in nodes}) == 4
    edges = [e['data'] for e in graph['edges'] if e['data']['edgeKind'] == 'datatype-property']
    assert {e['source'] for e in edges} == {
        'https://example.org/ontology#Local', 'https://external.example/Element', 'https://external.example/Other',
    }
    assert len(edges) == 3
    assert all([p['href'] for p in e['properties']] == ['#code'] for e in edges)
