from pathlib import Path
import pytest

pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from ontolens.deployment import create_container_app
from ontolens.web import create_app
from test_project import fixture

HEADERS = {'X-Ontolens-Write': '1'}


def setup_runtime(tmp_path, monkeypatch):
    root = tmp_path / 'data'
    static = tmp_path / 'frontend'
    static.mkdir()
    (static / 'index.html').write_text('<html>REACT-ENTRY</html>')
    monkeypatch.setenv('ONTOLENS_DATA_ROOT', str(root))
    monkeypatch.setenv('ONTOLENS_STATIC_DIR', str(static))
    return root, TestClient(create_container_app())


def test_container_bootstrap_and_static_routes(tmp_path, monkeypatch):
    root, client = setup_runtime(tmp_path, monkeypatch)
    assert client.get('/').text == '<html>REACT-ENTRY</html>'
    assert client.get('/api/health').json()['status'] == 'ok'
    assert client.get('/api/project').json()['ontologies'] == []
    assert client.get('/api/runtime').json() == {'file_browser': True, 'root': str(root), 'host_directory': None, 'host_source': ''}
    config = root / 'ontolens.project.yaml'
    before = config.read_bytes()
    create_container_app()
    assert config.read_bytes() == before
    assert client.get('/api/not-an-endpoint').status_code == 404
    assert client.post('/api/dialog/input', headers=HEADERS).status_code == 409


def test_browser_boundaries_and_open_existing_workspace(tmp_path, monkeypatch):
    root, client = setup_runtime(tmp_path, monkeypatch)
    project_dir = root / 'existing'
    project_dir.mkdir()
    config, _ = fixture(project_dir)
    listing = client.get('/api/files').json()
    assert listing['parent'] is None
    assert any(entry['name'] == 'existing' and entry['directory'] for entry in listing['entries'])
    assert client.get('/api/files', params={'path': str(tmp_path)}).status_code == 403
    assert client.get('/api/files', params={'path': str(root / '..')}).status_code == 403
    assert client.get('/api/files', params={'path': str(root / 'missing')}).status_code == 422
    assert client.post('/api/projects/open', json={'path': str(config)}).status_code == 403
    opened = client.post('/api/projects/open', headers=HEADERS, json={'path': str(config)})
    assert opened.status_code == 200, opened.text
    base = opened.json()['project']['base']
    # Dynamic mounts must win over the static frontend catch-all.
    assert client.get(base + '/api/project').json()['config'] == str(config)
    assert client.get('/').status_code == 200
    assert client.post('/api/projects/open', headers=HEADERS, json={'path': str(tmp_path / 'outside.yaml')}).status_code == 403
    restarted = TestClient(create_container_app())
    assert restarted.get(base + '/api/project').status_code == 200


def test_host_drive_shortcut(tmp_path, monkeypatch):
    root, client = setup_runtime(tmp_path, monkeypatch)
    drive = root / 'host-drive'
    drive.mkdir()
    monkeypatch.setenv('ONTOLENS_HOST_DIRECTORY', str(drive))
    assert client.get('/api/runtime').json()['host_directory'] == str(drive)
    assert client.get('/api/files', params={'path': str(drive)}).status_code == 200
    monkeypatch.setenv('ONTOLENS_HOST_DIRECTORY', str(tmp_path))
    assert client.get('/api/runtime').json()['host_directory'] is None


def test_windows_paths_and_directory_creation(tmp_path, monkeypatch):
    root, client = setup_runtime(tmp_path, monkeypatch)
    drive = root / 'host-drive'
    drive.mkdir()
    monkeypatch.setenv('ONTOLENS_HOST_DIRECTORY', str(drive))
    monkeypatch.setenv('ONTOLENS_HOST_SOURCE', 'D:/')
    response=client.get('/api/files', params={'path':'"d:\\"'})
    assert response.status_code == 200, response.text
    assert response.json()['path'] == str(drive)
    assert response.json()['display_path'] == 'D:\\'
    for path in ['C:\\', 'D:relative', 'D:\\..\\outside', '\\\\server\\share']:
        assert client.get('/api/files', params={'path':path}).status_code == 403
    body={'parent':'D:\\','name':'New project'}
    assert client.post('/api/files/directory', json=body).status_code == 403
    created=client.post('/api/files/directory', headers=HEADERS, json=body)
    assert created.status_code == 200, created.text
    assert (drive/'New project').is_dir()
    assert created.json()['display_path'] == 'D:\\New project'
    assert client.post('/api/files/directory', headers=HEADERS, json=body).status_code == 409
    for name in ['../outside','a/b','a\\b','CON','nul.txt','trailing.', 'space ', '..']:
        assert client.post('/api/files/directory',headers=HEADERS,json=body|{'name':name}).status_code == 422
    assert client.post('/api/files/directory',headers=HEADERS,json={'parent':str(tmp_path),'name':'outside'}).status_code == 403
    monkeypatch.setenv('ONTOLENS_HOST_SOURCE', 'D:/Projects')
    assert client.get('/api/files', params={'path':'D:\\Projects'}).status_code == 200
    assert client.get('/api/files', params={'path':'D:\\Other'}).status_code == 403


def test_container_create_and_build_project(tmp_path, monkeypatch):
    root, client = setup_runtime(tmp_path, monkeypatch)
    inputs = root / 'inputs'
    inputs.mkdir()
    fixture(inputs)
    created = client.post('/api/projects', headers=HEADERS, json={
        'name': 'Docker project', 'directory': str(root),
        'ontologies': [str(inputs / 'ontology.ttl')], 'copy_sources': True,
    })
    assert created.status_code == 200, created.text
    base = created.json()['project']['base']
    project = client.get(base + '/api/project').json()
    export = client.post(base + '/api/portal/export', headers=HEADERS, json={
        'revision': project['revision'], 'title': 'Container portal',
        'ontologies': [project['ontologies'][0]['id']], 'theme': 'both',
    })
    assert export.status_code == 200, export.text
    result = export.json()['portal']['result']
    for variant in result['variants'].values():
        assert client.get(variant['preview']).status_code == 200
    assert client.get(result['download']).status_code == 200
    restarted = TestClient(create_container_app())
    assert restarted.get(result['preview']).status_code == 200


def test_desktop_mode_retains_native_picker(tmp_path, monkeypatch):
    monkeypatch.delenv('ONTOLENS_DATA_ROOT', raising=False)
    monkeypatch.delenv('ONTOLENS_STATIC_DIR', raising=False)
    config, _ = fixture(tmp_path)
    client = TestClient(create_app(config))
    assert client.get('/api/runtime').json()['file_browser'] is False
    assert client.get('/api/files').status_code == 404
    calls = []

    def picker(kind, initial, language):
        calls.append((kind, language))
        return str(config)

    monkeypatch.setattr('ontolens.web.choose_local_path', picker)
    assert client.post('/api/projects/open?ui_language=en', headers=HEADERS, json={}).status_code == 200
    assert client.post('/api/dialog/input', headers=HEADERS).status_code == 200
    assert client.post('/api/projects/dialog/directory?ui_language=en', headers=HEADERS).status_code == 200
    assert calls == [('project', 'en'), ('input', 'de'), ('output', 'en')]
