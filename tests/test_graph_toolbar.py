from bs4 import BeautifulSoup
import pytest

from ontolens.pdf_export import PdfOptions, prepare_html
from ontolens.render import generate
from test_content import ONTOLOGY


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_graph_toolbar_separates_controls_and_legends(tmp_path, theme):
    source = tmp_path / 'toolbar.ttl'
    source.write_text(ONTOLOGY + '''
ex:external a owl:ObjectProperty ; rdfs:domain ex:Thing ; rdfs:range <https://w3id.org/tempo#Class> .
''', encoding='utf-8')
    output = generate(source, tmp_path / 'toolbar.html', theme=theme)
    soup = BeautifulSoup(output.read_text(encoding='utf-8'), 'html.parser')
    assert soup.html['data-theme'] == theme
    assert len(soup.select('.graph-filters input[checked]')) == 2
    for name in ['reset-graph-layout', 'fullscreen-graph', 'zoom-in-graph', 'zoom-out-graph', 'fit-graph']:
        button = soup.select_one(f'.graph-tools #{name}')
        assert button['title'] == button['aria-label']
        assert button.svg
    menu = soup.select_one('details#graph-export')
    assert 'open' not in menu.attrs
    assert menu.summary['aria-label'] == 'Export graph'
    assert len(menu.select('button')) == 3
    focus = soup.select_one('#graph-focus-bar')
    assert 'hidden' in focus.attrs
    assert focus.select_one('#graph-focus-title[role=status]')
    assert focus.select_one('#show-entire-graph')
    assert not soup.select_one('.visualization-actions #graph-focus-title')
    legend = soup.select_one('details.graph-legend')
    assert 'open' in legend.attrs
    assert legend.select_one('.graph-type-legend .subclass-legend svg')
    tempo = legend.select_one('[data-ontology="https://w3id.org/tempo#"]')
    assert tempo['title'] == 'https://w3id.org/tempo#'
    assert tempo.select_one('.ontology-legend-name').text == 'tempo'
    assert '--swatch-color:' in tempo.select_one('.ontology-swatch')['style']

    pdf_html = prepare_html(output, PdfOptions(graph=True))[0]
    pdf = BeautifulSoup(pdf_html, 'html.parser')
    assert pdf.select_one('#visualization .ontology-swatch')
    assert pdf.select_one('#visualization .subclass-legend')
    assert not pdf.select_one('#graph-export, #graph-focus-bar, .graph-tools')
