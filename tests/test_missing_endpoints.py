import json
import re
from pathlib import Path

from ontolens.cli import main
from ontolens.parser import load_ontology
from ontolens.render import _visualization_data
from test_content import ONTOLOGY

EXTRA = '''
ex:domainOnly a owl:ObjectProperty ; rdfs:domain ex:Thing .
ex:rangeOnly a owl:ObjectProperty ; rdfs:range ex:Thing .
ex:neither a owl:ObjectProperty .
ex:anotherDomainOnly a owl:ObjectProperty ; rdfs:domain ex:Thing .
ex:externalDomain a owl:ObjectProperty ; rdfs:domain <https://external.example/Class> .
ex:dataOnly a owl:DatatypeProperty ; rdfs:domain ex:Thing .
ex:dataNeither a owl:DatatypeProperty .
'''


def graph(path):
    match = re.search(r'window\.ontolensVisualization = (.*);', Path(path).read_text(encoding='utf-8'))
    return json.loads(match[1])['elements']


def test_missing_endpoints_are_opt_in_and_not_quality_fixes(tmp_path):
    source = tmp_path / 'test.ttl'
    source.write_text(ONTOLOGY + EXTRA, encoding='utf-8')
    doc = load_ontology(source, quality_report=True)
    before = doc.quality
    normal = _visualization_data(doc)['elements']
    enabled = _visualization_data(doc, True, 'de')['elements']
    assert not any(n['data']['kind'] == 'missing-endpoint' for n in normal['nodes'])
    placeholders = {n['data']['id']: n['data'] for n in enabled['nodes'] if n['data']['kind'] == 'missing-endpoint'}
    assert len(placeholders) == 4
    assert {n['label'] for n in placeholders.values()} == {''}
    uri = 'https://example.org/ontology#'
    edges = [e['data'] for e in enabled['edges']]
    assert any(e['source'] == uri + 'Thing' and e['target'] == 'missing-range:' + uri + 'domainOnly' for e in edges)
    assert any(e['source'] == 'missing-domain:' + uri + 'rangeOnly' and e['target'] == uri + 'Thing' for e in edges)
    assert not any('neither' in e.get('href', '') for e in edges)
    assert [e for e in enabled['edges'] if e['data']['edgeKind'] == 'datatype-property'] == [e for e in normal['edges'] if e['data']['edgeKind'] == 'datatype-property']
    assert doc.quality == before
    messages = [issue.message for section in doc.quality.sections for issue in section.issues]
    assert any('domainOnly' in m and 'range' in m for m in messages)
    assert any('rangeOnly' in m and 'domain' in m for m in messages)


def test_cli_and_project_flag(tmp_path):
    source = tmp_path / 'test.ttl'
    source.write_text(ONTOLOGY + EXTRA, encoding='utf-8')
    assert main([str(source), '-o', str(tmp_path / 'yes.html'), '--show-missing-endpoints', '--quality-report']) == 0
    assert any(n['data']['kind'] == 'missing-endpoint' for n in graph(next(tmp_path.rglob('yes.html')))['nodes'])
    config = tmp_path / 'project.yaml'
    config.write_text('name: test\noutput: output\ndefaults:\n  show_missing_endpoints: true\nontologies:\n  - id: test\n    input: test.ttl\n')
    assert main(['build', str(config), '--no-show-missing-endpoints']) == 0
    assert not any(n['data']['kind'] == 'missing-endpoint' for n in graph(next((tmp_path / 'output').rglob('test.html')))['nodes'])


def test_external_object_property_endpoints_are_visible_by_default(tmp_path):
    source = tmp_path / 'external.ttl'
    source.write_text(ONTOLOGY + '''
ex:outgoing a owl:ObjectProperty ; rdfs:domain ex:Thing ;
    rdfs:range <https://external.example/Class> .
ex:incoming a owl:ObjectProperty ; rdfs:domain <https://external.example/Class> ;
    rdfs:range ex:Thing .
ex:multiple a owl:ObjectProperty ; rdfs:domain ex:Thing ;
    rdfs:range ex:Thing, <https://external.example/Class> .
''', encoding='utf-8')
    doc = load_ontology(source)
    elements = _visualization_data(doc)['elements']
    external = [n['data'] for n in elements['nodes'] if n['data']['kind'] == 'external-class']
    assert len(external) == 1
    assert external[0]['id'] == 'https://external.example/Class'
    local = 'https://example.org/ontology#Thing'
    edges = [e['data'] for e in elements['edges']]
    assert any(e['source'] == local and e['target'] == external[0]['id'] for e in edges)
    assert any(e['source'] == external[0]['id'] and e['target'] == local for e in edges)
    assert sum(e['href'] == '#multiple' for e in edges) == 2
    assert not any(n['data']['kind'] == 'missing-endpoint' for n in elements['nodes'])
    assert main([str(source), '-o', str(tmp_path / 'external.html')]) == 0
    html = next(tmp_path.rglob('external.html')).read_text(encoding='utf-8')
    assert 'id="toggle-external-references" checked' in html
    assert 'id="toggle-datatype-properties" checked' in html


def test_web_setting_and_export(tmp_path):
    import pytest
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from ontolens.web import create_app
    source = tmp_path / 'test.ttl'
    source.write_text(ONTOLOGY + EXTRA, encoding='utf-8')
    config = tmp_path / 'project.yaml'
    config.write_text('ontologies:\n  - id: test\n    input: test.ttl\n')
    client = TestClient(create_app(config))
    headers = {'X-Ontolens-Write': '1'}
    revision = client.get('/api/project').json()['revision']
    settings = client.patch('/api/ontologies/test/settings', headers=headers, json={
        'revision': revision, 'quality_report': True, 'recommendations': False,
        'custom_annotations': False, 'check_content': False, 'show_missing_endpoints': True,
    })
    assert settings.status_code == 200
    result = client.post('/api/ontologies/test/export', headers=headers, json={
        'revision': settings.json()['revision'], 'kind': 'reference',
    })
    assert result.status_code == 200, result.text
    assert any(n['data']['kind'] == 'missing-endpoint' for n in graph(result.json()['path'])['nodes'])
    assert any('domainOnly' in n and 'range' in n for n in result.json()['notices'])
