import json
import re

from bs4 import BeautifulSoup

from ontolens.parser import load_ontology
from ontolens.pdf_export import PdfOptions, prepare_html
from ontolens.render import _visualization_data, generate
from test_content import ONTOLOGY


def test_subclass_labels_move_to_legend(tmp_path):
    source = tmp_path / 'hierarchy.ttl'
    source.write_text(ONTOLOGY + '\nex:Child a owl:Class ; rdfs:subClassOf ex:Thing .', encoding='utf-8')
    graph = _visualization_data(load_ontology(source))['elements']
    hierarchy = [e['data'] for e in graph['edges'] if e['data']['edgeKind'] == 'subClassOf']
    assert len(hierarchy) == 1
    assert hierarchy[0]['label'] == ''
    assert hierarchy[0]['source'].endswith('#Child')
    assert hierarchy[0]['target'].endswith('#Thing')
    assert hierarchy[0]['id'].startswith('subClassOf:')
    assert any(e['data']['label'] == 'related to' for e in graph['edges'])
    generate(source, tmp_path / 'hierarchy.html')
    html_path = next(tmp_path.rglob('hierarchy.html'))
    soup = BeautifulSoup(html_path.read_text(encoding='utf-8'), 'html.parser')
    assert soup.select_one('.subclass-legend svg path')
    assert soup.select_one('.subclass-legend').get_text() == 'rdfs:subClassOf'
    pdf_html = prepare_html(html_path, PdfOptions(graph=True))[0]
    assert BeautifulSoup(pdf_html, 'html.parser').select_one('#visualization .subclass-legend svg')
    assert 'subclass-legend' not in prepare_html(html_path, PdfOptions(graph=False))[0]

    # Old snapshots gain the legend when exported to PDF too.
    soup.select_one('.graph-type-legend').decompose()
    for edge in graph['edges']:
        if edge['data']['edgeKind'] == 'subClassOf':
            edge['data']['label'] = 'subClassOf'
    script = next(s for s in soup.find_all('script') if 'window.ontolensVisualization =' in s.get_text())
    script.string = re.sub(r'window\.ontolensVisualization = .*;',
                          'window.ontolensVisualization = ' + json.dumps({'elements': graph}) + ';', script.get_text())
    legacy = tmp_path / 'legacy.html'
    legacy.write_text(str(soup), encoding='utf-8')
    legacy_pdf = prepare_html(legacy, PdfOptions(graph=True))[0]
    assert BeautifulSoup(legacy_pdf, 'html.parser').select_one('.subclass-legend svg')
