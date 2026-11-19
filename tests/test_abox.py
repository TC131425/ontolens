import json
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from ontolens.abox_parser import load_abox
from ontolens.abox_render import generate_abox, render_abox
from ontolens.cli import main


SOURCE = '''@prefix ex: <https://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:Person a owl:Class .
ex:p a owl:ObjectProperty .
ex:a a ex:Person; rdfs:label "Person A"@en, "Person A DE"@de;
 ex:p ex:b, ex:outside; ex:count 0; ex:active false;
 ex:detail [ ex:value "</script><script>alert(1)</script>" ] .
ex:b ex:p ex:a .
ex:dual a owl:Class, ex:Person .
'''


def test_instances_values_schema_punning_and_references(tmp_path):
    source = tmp_path / 'input.ttl'
    source.write_text(SOURCE, encoding='utf-8')
    doc = load_abox(source)
    nodes = {n.resource.id: n for n in doc.instances}
    assert 'https://example.org/Person' not in nodes
    assert 'https://example.org/p' not in nodes
    assert 'https://example.org/dual' in nodes
    assert not nodes['https://example.org/b'].external
    assert nodes['https://example.org/outside'].external
    assert any(n.blank for n in doc.instances)
    assert nodes['https://example.org/a'].resource.label == 'Person A DE'
    assert {'0', 'false'} <= {v.value for v in nodes['https://example.org/a'].values}
    assert len(doc.relations) == 4
    soup = BeautifulSoup(render_abox(doc), 'html.parser')
    payload = json.loads(soup.select_one('#abox-data').string)
    assert len(payload['instances']) == len(nodes)
    assert len(soup.find_all('script')) == 8
    assert 'alert(1)' not in ''.join(s.get_text() for s in soup.find_all('script') if not s.get('type'))


@pytest.mark.parametrize('rdf_format,suffix', [('turtle','.ttl'),('xml','.rdf'),('nt','.nt'),('json-ld','.jsonld')])
def test_formats_and_offline_bundle(tmp_path, rdf_format, suffix):
    from rdflib import Graph
    path = tmp_path / ('input' + suffix)
    Graph().parse(data=SOURCE, format='turtle').serialize(path, format=rdf_format)
    page = generate_abox(path, tmp_path / 'out.html')
    soup = BeautifulSoup(page.read_text(encoding='utf-8'), 'html.parser')
    assert not soup.select('script[src],link[rel="stylesheet"][href]')
    assert not (page.parent / 'assets').exists()
    assert soup.select_one('style[data-ontolens-asset="abox.css"]')
    assert soup.select_one('script[data-ontolens-asset="abox.js"]').find_previous('script', id='abox-data')
    assert (page.parent / 'downloads' / path.name).read_bytes() == path.read_bytes()
    assert len(load_abox(path).relations) == 4


def test_empty_and_invalid_input(tmp_path):
    path = tmp_path / 'empty.ttl'
    path.write_text('')
    assert not load_abox(path).instances
    with pytest.raises(SystemExit):
        main(['abox', str(path), '--max-nodes', '0'])
    path.write_text('this is not turtle')
    with pytest.raises(SystemExit):
        main(['abox', str(path)])
