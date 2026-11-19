import io
from pathlib import Path
from zipfile import ZipFile
import pytest
from bs4 import BeautifulSoup
from ontolens.render import generate
from ontolens.cli import main
from test_project import fixture


def assert_theme(path, theme):
    html = Path(path).read_text(encoding='utf-8')
    assert BeautifulSoup(html, 'html.parser').html['data-theme'] == theme
    assert 'document-dark-mode' not in html
    assert 'ontolens-theme:' not in html


def test_both_cli_and_combined(tmp_path):
    config, _ = fixture(tmp_path)
    md = tmp_path / 'intro.md'
    md.write_text('# Introduction\nBoth variants.', encoding='utf-8')
    page = generate(tmp_path / 'ontology.ttl', tmp_path / 'combined.html', content_path=md, theme='both')
    for theme in ('light', 'dark'):
        variant = page.parent.parent / theme / page.name
        assert_theme(variant, theme)
        assert 'Both variants.' in variant.read_text(encoding='utf-8')
        assert (variant.parent / 'downloads/ontology.ttl').is_file()
    assert main(['build', str(config), '--theme', 'both']) == 0
    root = next((tmp_path / 'out').iterdir())
    for theme in ('light', 'dark'):
        assert_theme(root / theme / 'index.html', theme)
        for document in (root / theme).rglob('first.html'):
            assert_theme(document, theme)
            soup = BeautifulSoup(document.read_text(encoding='utf-8'), 'html.parser')
            assert (document.parent / soup.select_one('nav[aria-label="Portal"] a')['href']).resolve() == root / theme / 'index.html'


@pytest.mark.parametrize('portal', [False, True])
def test_both_api_restart_zip_and_unlink(tmp_path, portal):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from ontolens.web import create_app
    config, _ = fixture(tmp_path)
    client = TestClient(create_app(config))
    headers = {'X-Ontolens-Write': '1'}
    revision = client.get('/api/project').json()['revision']
    if portal:
        response = client.post('/api/portal/export', headers=headers, json={'revision': revision, 'title': 'Both', 'ontologies': ['first'], 'theme': 'both'})
        assert response.status_code == 200, response.text
        result = response.json()['portal']['result']
    else:
        settings = client.patch('/api/ontologies/first/settings', headers=headers, json={
            'revision': revision, 'theme': 'both', 'quality_report': False, 'recommendations': False,
            'custom_annotations': False, 'check_content': False,
        })
        assert settings.status_code == 200
        revision = settings.json()['revision']
        response = client.post('/api/ontologies/first/export', headers=headers, json={'revision': revision, 'kind': 'reference'})
        assert response.status_code == 200, response.text
        result = response.json()
    assert set(result['variants']) == {'light', 'dark'}
    client = TestClient(create_app(config))
    for theme, variant in result['variants'].items():
        assert_theme(variant['path'], theme)
        response = client.get(variant['preview'])
        assert response.status_code == 200
        assert BeautifulSoup(response.text, 'html.parser').html['data-theme'] == theme
    with ZipFile(io.BytesIO(client.get(result['download']).content)) as archive:
        assert any(n.startswith('light/') and n.endswith('.html') for n in archive.namelist())
        assert any(n.startswith('dark/') and n.endswith('.html') for n in archive.namelist())
    url = '/api/portal/html' if portal else '/api/ontologies/first/html/reference'
    assert client.put(url, headers=headers, json={'revision': revision}).status_code == 200
    for variant in result['variants'].values():
        assert client.get(variant['preview']).status_code == 404
        assert Path(variant['path']).is_file()
