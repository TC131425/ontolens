import pytest

pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from ontolens.web import create_app
from test_project import fixture

HEADERS = {'X-Ontolens-Write': '1'}


def test_remove_all_persists_and_reopen(tmp_path, monkeypatch):
    monkeypatch.setenv('ONTOLENS_DATA_ROOT', str(tmp_path))
    config, _ = fixture(tmp_path)
    original = config.read_bytes()
    client = TestClient(create_app(config))
    entry = client.get('/api/projects').json()['projects'][0]
    url = f"/api/projects/{entry['id']}"
    assert client.delete(url).status_code == 403
    assert client.delete(url, headers=HEADERS).json()['files_preserved']
    assert client.delete(url, headers=HEADERS).status_code == 404
    restarted = TestClient(create_app(config))
    assert restarted.get('/api/projects').json() == {'projects': [], 'default': None}
    assert config.read_bytes() == original
    assert (tmp_path / 'ontology.ttl').is_file()
    assert restarted.post('/api/projects/open', headers=HEADERS, json={'path': str(config)}).status_code == 200
    assert len(restarted.get('/api/projects').json()['projects']) == 1


def test_remove_mounted_project_and_reopen(tmp_path, monkeypatch):
    monkeypatch.setenv('ONTOLENS_DATA_ROOT', str(tmp_path))
    config, _ = fixture(tmp_path)
    other = tmp_path / 'other.yaml'
    other.write_bytes(config.read_bytes())
    client = TestClient(create_app(config))
    entry = client.post('/api/projects/open', headers=HEADERS, json={'path': str(other)}).json()['project']
    assert client.get(entry['base'] + '/api/project').status_code == 200
    assert client.delete(f"/api/projects/{entry['id']}", headers=HEADERS).status_code == 200
    assert client.get(entry['base'] + '/api/project').status_code == 404
    assert other.is_file()
    reopened = client.post('/api/projects/open', headers=HEADERS, json={'path': str(other)}).json()['project']
    assert client.get(reopened['base'] + '/api/project').status_code == 200
