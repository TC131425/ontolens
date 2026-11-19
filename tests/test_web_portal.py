import io
import shutil
from pathlib import Path
from urllib.parse import urljoin
from zipfile import ZipFile

import pytest
pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from bs4 import BeautifulSoup
from ontolens.web import create_app, create_project_app
from test_project import fixture

HEADERS = {'X-Ontolens-Write': '1'}


def test_portal_selection_download_navigation_restart_and_move(tmp_path):
    config, _ = fixture(tmp_path)
    original = config.read_bytes()
    client = TestClient(create_app(config))
    revision = client.get('/api/project').json()['revision']
    response = client.post('/api/portal/export', headers=HEADERS, json={
        'revision': revision, 'title': 'Selected <Portal>', 'ontologies': ['first'],
    })
    assert response.status_code == 200, response.text
    project = response.json()
    portal = project['portal']
    assert portal['selection'] == ['first']
    result = portal['result']
    assert project['ontologies'][0]['html']['reference'] is None
    assert config.read_bytes() == original
    page = client.get(result['preview'])
    assert page.status_code == 200
    soup = BeautifulSoup(page.text, 'html.parser')
    assert soup.h1.get_text() == 'Selected <Portal>'
    assert len(soup.select('article')) == 1
    document_url = urljoin(result['preview'], soup.select_one('h2 a')['href'])
    document = client.get(document_url)
    assert document.status_code == 200
    document_soup = BeautifulSoup(document.text, 'html.parser')
    back = document_soup.select_one('nav[aria-label="Portal"] a')['href']
    assert urljoin(document_url, back) == result['preview']
    source = document_soup.select_one('a[href="downloads/ontology.ttl"]')['href']
    assert client.get(urljoin(document_url, source)).status_code == 200
    with ZipFile(io.BytesIO(client.get(result['download']).content)) as archive:
        assert 'index.html' in archive.namelist()
        assert not any(name.startswith('second/') for name in archive.namelist())
    restarted = TestClient(create_app(config))
    assert restarted.get(result['preview']).status_code == 200
    moved = tmp_path.parent / (tmp_path.name + '-moved')
    shutil.copytree(tmp_path, moved)
    relocated = TestClient(create_app(moved / config.name))
    restored = relocated.get('/api/project').json()['portal']['result']
    assert Path(restored['path']).is_relative_to(moved)
    assert relocated.get(restored['preview']).status_code == 200
    assert relocated.get(restored['download']).status_code == 200
    private = result['preview'].rsplit('/', 1)[0] + '/unrelated.txt'
    (Path(result['path']).parent / 'unrelated.txt').write_text('private')
    assert client.get(private).status_code == 404


def test_portal_validation_and_failure_preserves_previous_output(tmp_path):
    config, _ = fixture(tmp_path)
    client = TestClient(create_app(config))
    revision = client.get('/api/project').json()['revision']
    request = {'revision': revision, 'title': 'Portal', 'ontologies': ['first']}
    assert client.post('/api/portal/export', json=request).status_code == 403
    for change, status in [({'ontologies': []}, 422), ({'ontologies': ['missing']}, 422),
                           ({'title': ' '}, 422), ({'revision': 'stale'}, 409)]:
        assert client.post('/api/portal/export', headers=HEADERS, json=request | change).status_code == status
    success = client.post('/api/portal/export', headers=HEADERS, json=request)
    assert success.status_code == 200
    previous = success.json()['portal']['result']
    (tmp_path / 'ontology.ttl').unlink()
    assert client.post('/api/portal/export', headers=HEADERS, json=request).status_code == 409
    assert client.get('/api/project').json()['portal']['result'] == previous


@pytest.mark.parametrize('theme', ['light', 'dark'])
def test_portal_theme_and_assignment_lifecycle(tmp_path, theme):
    config, _ = fixture(tmp_path)
    client = TestClient(create_app(config))
    revision = client.get('/api/project').json()['revision']
    request = {'revision': revision, 'title': 'Portal', 'ontologies': ['first', 'second'], 'theme': theme}
    response = client.post('/api/portal/export', headers=HEADERS, json=request)
    assert response.status_code == 200, response.text
    result = response.json()['portal']['result']
    soup = BeautifulSoup(client.get(result['preview']).text, 'html.parser')
    assert soup.html['data-theme'] == theme
    assert soup.select_one('#document-dark-mode') is None
    for link in soup.select('h2 a'):
        doc = BeautifulSoup(client.get(urljoin(result['preview'], link['href'])).text, 'html.parser')
        assert doc.html['data-theme'] == theme
    assert client.post('/api/portal/export', headers=HEADERS, json=request).status_code == 409
    before = Path(result['path']).read_bytes()
    assert client.put('/api/portal/html', json={'revision': revision}).status_code == 403
    assert client.put('/api/portal/html', headers=HEADERS, json={'revision': 'stale'}).status_code == 409
    detached = client.put('/api/portal/html', headers=HEADERS, json={'revision': revision})
    assert detached.status_code == 200
    assert detached.json()['portal']['result'] is None
    assert detached.json()['portal']['theme'] == theme
    assert client.get(result['preview']).status_code == 404
    restarted = TestClient(create_app(config))
    assert restarted.get('/api/project').json()['portal']['result'] is None
    assert restarted.put('/api/portal/html', headers=HEADERS, json={'revision': revision, 'path': str(tmp_path / 'missing.html')}).status_code == 422
    assigned = restarted.put('/api/portal/html', headers=HEADERS, json={'revision': revision, 'path': result['path']})
    assert assigned.status_code == 200
    manual = assigned.json()['portal']['result']
    assert manual['downloadLabel'] == 'HTML herunterladen'
    assert restarted.get(manual['preview']).status_code == 200
    assert restarted.get(manual['download']).content == before
    assert Path(result['path']).read_bytes() == before


def test_portal_uses_assigned_markdown_and_workspace_prefix(tmp_path):
    config, _ = fixture(tmp_path)
    from fastapi import FastAPI
    app = FastAPI()
    app.mount('/workspaces/test', create_project_app(config, '/workspaces/test'))
    client = TestClient(app)
    base = '/workspaces/test/api'
    revision = client.get(base + '/project').json()['revision']
    md = tmp_path / 'content.md'
    md.write_text('# Introduction\nUnique portal editorial content.', encoding='utf-8')
    project = client.patch(base + '/ontologies/first/path', headers=HEADERS,
                           json={'revision': revision, 'kind': 'content', 'path': str(md)}).json()
    response = client.post(base + '/portal/export', headers=HEADERS,
                           json={'revision': project['revision'], 'title': 'Both', 'ontologies': ['first', 'second']})
    assert response.status_code == 200, response.text
    result = response.json()['portal']['result']
    assert result['preview'].startswith(base)
    soup = BeautifulSoup(client.get(result['preview']).text, 'html.parser')
    assert len(soup.select('h2 a')) == 2
    for link in soup.select('h2 a'):
        page = client.get(urljoin(result['preview'], link['href']))
        assert page.status_code == 200
        assert ('Unique portal editorial content.' in page.text) == link['href'].startswith('first/')
