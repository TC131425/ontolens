from pathlib import Path
import pytest
pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from ontolens.web import create_app
from ontolens.project import load_project
from test_project import fixture

HEADERS = {'X-Ontolens-Write': '1'}


def test_add_copy_images_remove_and_readd(tmp_path):
    config, _ = fixture(tmp_path)
    external = tmp_path / 'external'
    external.mkdir()
    source = external / 'new.ttl'
    source.write_text((tmp_path / 'ontology.ttl').read_text() + '\n<https://example.org/ontology> rdfs:comment "![Figure](figure.svg)"@en .', encoding='utf-8')
    (external / 'figure.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    original = source.read_bytes()
    client = TestClient(create_app(config))
    revision = client.get('/api/project').json()['revision']
    request = {'revision': revision, 'paths': [str(source), str(source)], 'copy_sources': True}
    assert client.post('/api/ontologies', json=request).status_code == 403
    added = client.post('/api/ontologies', headers=HEADERS, json=request)
    assert added.status_code == 200, added.text
    project = added.json()
    assert len(project['ontologies']) == 3
    item = project['ontologies'][-1]
    assert Path(item['input']).is_relative_to(tmp_path / 'sources')
    assert (Path(item['input']).parent / 'img/figure.svg').is_file()
    assert source.read_bytes() == original
    assert 'input: sources/' in config.read_text()
    assert client.post('/api/ontologies', headers=HEADERS, json=request).status_code == 409
    duplicate = client.post('/api/ontologies', headers=HEADERS, json={'revision': project['revision'], 'paths': [item['input']]})
    assert len(duplicate.json()['ontologies']) == 3
    export = client.post(f"/api/ontologies/{item['id']}/export", headers=HEADERS,
                         json={'revision': project['revision'], 'kind': 'reference'}).json()
    removed = client.post(f"/api/ontologies/{item['id']}/remove", headers=HEADERS, json={'revision': project['revision']})
    assert removed.status_code == 200
    assert len(removed.json()['ontologies']) == 2
    assert Path(item['input']).is_file()
    assert Path(export['path']).is_file()
    assert client.get(export['preview']).status_code == 404
    again = client.post('/api/ontologies', headers=HEADERS, json=request | {'revision': removed.json()['revision']})
    assert again.status_code == 200
    assert again.json()['ontologies'][-1]['id'] != item['id']
    assert again.json()['ontologies'][-1]['html']['reference'] is None


def test_empty_project_and_external_addition(tmp_path, monkeypatch):
    config, _ = fixture(tmp_path)
    client = TestClient(create_app(config))
    for identity in ('first', 'second'):
        revision = client.get('/api/project').json()['revision']
        response = client.post(f'/api/ontologies/{identity}/remove', headers=HEADERS, json={'revision': revision})
        assert response.status_code == 200
    assert not load_project(config).ontologies
    assert client.get('/api/projects').json()['projects'][0]['available']
    revision = client.get('/api/project').json()['revision']
    source = tmp_path / 'ontology.ttl'
    monkeypatch.setattr('ontolens.web.choose_local_path', lambda *args: [str(source)])
    assert client.post('/api/dialog/ontologies', headers=HEADERS).json()['path'] == [str(source)]
    added = client.post('/api/ontologies', headers=HEADERS, json={'revision': revision, 'paths': [str(source)], 'copy_sources': False})
    assert added.status_code == 200
    assert added.json()['ontologies'][0]['input'] == str(source)
    assert not (tmp_path / 'sources').exists()
    restarted = TestClient(create_app(config))
    assert len(restarted.get('/api/project').json()['ontologies']) == 1


def test_invalid_addition_does_not_change_project(tmp_path):
    config, _ = fixture(tmp_path)
    client = TestClient(create_app(config))
    revision = client.get('/api/project').json()['revision']
    before = config.read_bytes()
    for paths in ([], [str(tmp_path / 'missing.ttl')], ['relative.ttl']):
        assert client.post('/api/ontologies', headers=HEADERS, json={'revision': revision, 'paths': paths}).status_code == 422
    assert config.read_bytes() == before
    assert client.post('/api/ontologies/missing/remove', headers=HEADERS, json={'revision': revision}).status_code == 404
    assert config.read_bytes() == before
