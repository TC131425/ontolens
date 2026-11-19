import io
import json
import os
from pathlib import Path
from zipfile import ZipFile

import pytest
from bs4 import BeautifulSoup

from ontolens.pdf_export import PdfOptions, prepare_html, render_pdf
from ontolens.render import generate
from test_content import ONTOLOGY
from test_project import fixture

HEADERS = {'X-Ontolens-Write': '1'}


def test_legacy_restrictions_keep_condition_and_number_together(tmp_path):
    source = tmp_path / 'old.html'
    source.write_text('''<html><body><table><tr><td><details><summary>Restrictions</summary>
        <ul class="restriction-list"><li><span class="restriction-property">Parent group</span>
        <span class="restriction-constraint">at least</span> <strong>0</strong>
        <span class="restriction-filler">of Group</span></li></ul></details></td></tr></table></body></html>''')
    html = prepare_html(source, PdfOptions())[0]
    soup = BeautifulSoup(html, 'html.parser')
    assert soup.select_one('tr.restriction-row')
    condition = soup.select_one('.restriction-condition')
    assert condition.get_text(' ', strip=True) == 'at least 0'
    assert condition.strong.get_text() == '0'
    assert not condition.select('.restriction-filler')


def test_prepare_pdf_is_light_static_complete_and_local(tmp_path):
    (tmp_path / 'image.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="30"><rect width="100" height="30" fill="red"/></svg>')
    source = tmp_path / 'page.html'
    source.write_text('''<html lang="de" data-theme="dark"><head><title>Test</title>
      <script>fetch("http://localhost/secrets")</script></head><body>
      <aside class="toc">old toc</aside><main><h1 id="intro">Einleitung</h1>
      <section id="classes"><h2>Classes</h2><details><summary>Restrictions</summary>Important restriction</details></section>
      <img src="image.svg" onload="alert(1)"><img src="https://example.org/remote.png" alt="Remote">
      <button>Export</button><iframe src="file:///etc/passwd"></iframe></main></body></html>''')
    before = source.read_bytes()
    html, _, graph, notices = prepare_html(source, PdfOptions())
    soup = BeautifulSoup(html, 'html.parser')
    assert soup.html['data-theme'] == 'light'
    assert soup.details.has_attr('open')
    assert 'Important restriction' in soup.get_text()
    assert not soup.select('script, button, iframe, aside.toc, [onload]')
    assert soup.img['src'].startswith('data:image/svg+xml;base64,')
    assert soup.select_one('.pdf-toc a[href="#intro"]')
    assert graph is None
    assert any('Online-Bild' in notice for notice in notices)
    assert not BeautifulSoup(prepare_html(source, PdfOptions(figures=False))[0], 'html.parser').find('img')
    assert source.read_bytes() == before


def test_missing_and_outside_images_fail(tmp_path):
    root = tmp_path / 'doc'
    root.mkdir()
    page = root / 'page.html'
    for ref in ('missing.png', '../secret.png'):
        page.write_text(f'<html><body><img src="{ref}"></body></html>')
        with pytest.raises(ValueError):
            prepare_html(page, PdfOptions())
        prepare_html(page, PdfOptions(figures=False))
    with pytest.raises(ValueError):
        PdfOptions(paper='A0')


def test_graph_retains_namespace_names_and_legacy_snapshots(tmp_path):
    source = tmp_path / 'ontology.ttl'
    source.write_text(ONTOLOGY + '\n<https://external.example/DictionaryReferenceDocument> a owl:Class .')
    page = generate(source, tmp_path / 'doc.html', include_external_classes=True)
    _, _, graph, _ = prepare_html(page, PdfOptions(graph=True))
    assert len(graph['nodes']) == 2
    assert graph['ontologies']
    assert any(n['data']['id'] == 'https://external.example/DictionaryReferenceDocument' for n in graph['nodes'])
    snapshot = {'elements': {'nodes': graph['nodes'], 'edges': graph['edges']}}
    legacy = tmp_path / 'legacy.html'
    legacy.write_text('<html><body><section id="visualization"><h2>Graph</h2></section>'
                      '<script>window.ontolensVisualization = ' + json.dumps(snapshot) + ';</script></body></html>')
    html, _, legacy_graph, _ = prepare_html(legacy, PdfOptions(graph=True))
    assert legacy_graph['ontologies'] == []
    assert len(legacy_graph['nodes']) == 2
    assert not BeautifulSoup(html, 'html.parser').find('script')


def test_api_selection_options_and_multiple_downloads(tmp_path, monkeypatch):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from ontolens.web import create_app
    config, _ = fixture(tmp_path)
    html = tmp_path / 'doc.html'
    html.write_text('<html><body>Saved snapshot</body></html>')
    config.with_suffix('.outputs.json').write_text(json.dumps({
        'first': {'reference': {'path': 'doc.html'}}, 'second': {'combined': {'path': 'doc.html'}}}))
    calls = []
    def fake_render(source, output, options, *, root):
        calls.append((source, options))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'%PDF-test')
        return ['Test notice']
    monkeypatch.setattr('ontolens.pdf_export.render_pdf', fake_render)
    client = TestClient(create_app(config))
    revision = client.get('/api/project').json()['revision']
    request = {'revision': revision, 'documents': [{'ontology': 'first', 'kind': 'reference'}]}
    assert client.post('/api/project/pdf', json=request).status_code == 403
    assert client.post('/api/project/pdf', headers=HEADERS, json=request | {'revision':'stale'}).status_code == 409
    assert client.post('/api/project/pdf', headers=HEADERS, json=request | {'documents':[]}).status_code == 422
    response = client.post('/api/project/pdf', headers=HEADERS, json=request)
    assert response.status_code == 200, response.text
    assert response.content == b'%PDF-test'
    assert calls[-1][1] == PdfOptions()
    request['documents'].append({'ontology': 'second', 'kind': 'combined'})
    response = client.post('/api/project/pdf', headers=HEADERS, json=request | {'paper':'A3', 'figures':False, 'graph':True})
    assert response.status_code == 200, response.text
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {'first-reference.pdf', 'second-combined.pdf'}
    assert calls[-1][1] == PdfOptions('A3', False, True)
    request['documents'] = [{'ontology': 'first', 'kind': 'combined'}]
    assert client.post('/api/project/pdf', headers=HEADERS, json=request).status_code == 422


@pytest.mark.skipif(os.environ.get('ONTOLENS_TEST_PDF') != '1', reason='Requires installed Chromium; enable ONTOLENS_TEST_PDF=1')
def test_real_pdf_pagination_links_outline_graph_and_cli(tmp_path):
    from pypdf import PdfReader
    from ontolens.cli import main
    source = tmp_path / 'ontology.ttl'
    source.write_text(ONTOLOGY + '\n<https://external.example/DictionaryReferenceDocument> a owl:Class .')
    html = generate(source, tmp_path / 'doc.html', theme='dark', quality_report=True, include_external_classes=True)
    original = html.read_bytes()
    target = tmp_path / 'result.pdf'
    render_pdf(html, target, PdfOptions(graph=True))
    reader = PdfReader(target)
    text = '\n'.join(page.extract_text() for page in reader.pages)
    assert 'Example ontology' in text and 'Classes' in text
    assert len(reader.pages) > 1
    assert reader.outline
    assert any(page.images for page in reader.pages)
    assert any(page.get('/Annots') for page in reader.pages)
    assert abs(float(reader.pages[0].mediabox.width) - 595) < 2
    landscape = [page for page in reader.pages if page.mediabox.width > page.mediabox.height]
    assert len(landscape) == 1
    assert landscape[0].images
    assert 'Visualization' in landscape[0].extract_text()
    assert abs(float(landscape[0].mediabox.width) - 842) < 2
    assert html.read_bytes() == original
    assert main(['pdf', str(html), '--paper', 'A3', '--no-figures', '-o', str(tmp_path / 'a3.pdf')]) == 0
    a3 = PdfReader(next(tmp_path.glob('*_a3/a3.pdf')))
    assert abs(float(a3.pages[0].mediabox.width) - 842) < 2
    assert all(page.mediabox.width < page.mediabox.height for page in a3.pages)
