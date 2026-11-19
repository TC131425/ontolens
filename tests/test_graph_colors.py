from dataclasses import replace

from bs4 import BeautifulSoup

from ontolens.parser import load_ontology
from ontolens.render import _visualization_data, generate
from ontolens.pdf_export import prepare_html, PdfOptions
from test_content import ONTOLOGY


def test_namespace_colors_and_legends(tmp_path):
    source = tmp_path / 'colors.ttl'
    source.write_text(ONTOLOGY + '''
@prefix a: <https://a.example/#> .
@prefix b: <https://b.example/> .
ex:p a owl:ObjectProperty ; rdfs:domain ex:Thing ; rdfs:range a:One, a:Two, b:Three .
ex:q a owl:ObjectProperty ; rdfs:domain ex:Thing .
''', encoding='utf-8')
    doc = load_ontology(source)
    graph = _visualization_data(doc, True)
    nodes = {n['data']['id']: n['data'] for n in graph['elements']['nodes']}
    assert nodes['https://a.example/#One']['color'] == nodes['https://a.example/#Two']['color']
    assert nodes['https://a.example/#One']['color'] != nodes['https://b.example/Three']['color']
    primary = nodes['https://example.org/ontology#Thing']['color']
    assert primary == '#155c63'
    assert nodes['missing-range:https://example.org/ontology#q']['color'] == primary
    assert len(graph['ontologies']) == 3
    assert _visualization_data(replace(doc, object_properties=tuple(reversed(doc.object_properties))), True)['ontologies'] == graph['ontologies']
    out = tmp_path / 'colors.html'
    generate(source, out, show_missing_endpoints=True)
    html_path = next(tmp_path.rglob('colors.html'))
    soup = BeautifulSoup(html_path.read_text(encoding='utf-8'), 'html.parser')
    assert len(soup.select('.ontology-legend [data-ontology]')) == 3
    pdf_html = prepare_html(html_path, PdfOptions(graph=True))[0]
    assert len(BeautifulSoup(pdf_html, 'html.parser').select('.ontology-legend [data-ontology]')) == 3
