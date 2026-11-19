import io
import json
from zipfile import ZipFile

import pytest
import yaml
pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from ontolens.project import load_project, build_project
from ontolens.web import create_app
from test_project import fixture

HEADERS = {'X-Ontolens-Write': '1'}


def export(client, include_outputs=False):
    return client.post('/api/project/archive', headers=HEADERS, json={
        'revision': client.get('/api/project').json()['revision'], 'include_outputs': include_outputs})


def test_portable_sources_markdown_images_and_no_mutation(tmp_path):
    config, document = fixture(tmp_path)
    external = tmp_path / 'external'
    external.mkdir()
    image = external / 'figure (1).svg'
    image.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    md = external / 'intro.md'
    md.write_text('---\ntitle: Example\nlanguage: en\n---\n# Intro\n'
                  '![Inline](<figure (1).svg>)\n\n![Reference][fig]\n\n[fig]: <figure (1).svg>\n\n'
                  f'<img src="{image.as_uri()}">\n\n<!-- ontolens:cross-reference -->', encoding='utf-8')
    document['ontologies'][0]['content'] = str(md)
    config.write_text(yaml.safe_dump(document))
    source = tmp_path / 'ontology.ttl'
    source.write_text(source.read_text() + '\n<https://example.org/test> <http://www.w3.org/2000/01/rdf-schema#comment> "![Figure](external/figure%20(1).svg)" .', encoding='utf-8')
    # Existing ontology copier supports the repository's simple Markdown image syntax.
    source.write_text(source.read_text().replace('external/figure%20(1).svg', 'external/figure%20%281%29.svg'), encoding='utf-8')
    before = {p: p.read_bytes() for p in [config, source, md, image]}
    client = TestClient(create_app(config))
    response = export(client)
    assert response.status_code == 200, response.text
    moved = tmp_path / 'unpacked'
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert not any('/build/' in name for name in archive.namelist())
        assert not any(name.endswith('.outputs.json') for name in archive.namelist())
        archive.extractall(moved)
    copied_config = moved / 'project/ontolens.project.yaml'
    copied = load_project(copied_config)
    assert copied.output == copied_config.parent / 'build'
    assert all(item.input.is_relative_to(copied_config.parent) for item in copied.ontologies)
    assert copied.ontologies[0].content.is_relative_to(copied_config.parent)
    assert md.as_uri() not in copied.ontologies[0].content.read_text()
    result = build_project(copied)
    assert result.portal.is_file()
    for path, content in before.items():
        assert path.read_bytes() == content


def test_includes_only_assigned_outputs_and_relinks_both_themes(tmp_path):
    config, _ = fixture(tmp_path)
    client = TestClient(create_app(config))
    revision = client.get('/api/project').json()['revision']
    result = client.post('/api/portal/export', headers=HEADERS, json={
        'revision': revision, 'title': 'Portal', 'ontologies': ['first', 'second'], 'theme': 'both'})
    assert result.status_code == 200, result.text
    original = config.with_suffix('.outputs.json').read_bytes()
    (tmp_path / 'out' / 'secret.txt').write_text('not part of an export')
    response = export(client, True)
    assert response.status_code == 200, response.text
    moved = tmp_path / 'unpacked'
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert not any('secret.txt' in name for name in archive.namelist())
        archive.extractall(moved)
    root = moved / 'project'
    assert str(tmp_path) not in (root / 'ontolens.project.yaml').read_text()
    relocated = TestClient(create_app(root / 'ontolens.project.yaml'))
    result = relocated.get('/api/project').json()['portal']['result']
    assert set(result['variants']) == {'light', 'dark'}
    for variant in result['variants'].values():
        assert relocated.get(variant['preview']).status_code == 200
    assert config.with_suffix('.outputs.json').read_bytes() == original


def test_validation_and_missing_images(tmp_path):
    config, document = fixture(tmp_path)
    client = TestClient(create_app(config))
    assert client.post('/api/project/archive', json={'revision': 'x'}).status_code == 403
    assert client.post('/api/project/archive', headers=HEADERS, json={'revision': 'old'}).status_code == 409
    md = tmp_path / 'missing.md'
    md.write_text('![missing](missing.png)')
    document['ontologies'][0]['content'] = str(md)
    config.write_text(yaml.safe_dump(document))
    response = export(client)
    assert response.status_code == 422
    assert 'missing.png' in response.json()['detail']


def test_empty_project_and_external_image_warning(tmp_path):
    config, document = fixture(tmp_path)
    md = tmp_path / 'online.md'
    md.write_text('![online](https://example.org/image.png)')
    document['ontologies'][0]['content'] = str(md)
    config.write_text(yaml.safe_dump(document))
    client = TestClient(create_app(config))
    response = export(client)
    assert response.status_code == 200
    assert any('Online-Bild' in notice for notice in json.loads(response.headers['X-Ontolens-Notices']))
    document['ontologies'] = []
    config.write_text(yaml.safe_dump(document))
    assert export(client).status_code == 200


def test_cli_package_and_missing_export_dependency(tmp_path):
    from ontolens.cli import main
    config, _ = fixture(tmp_path)
    assert main(['pack', str(config), '-o', str(tmp_path / 'share.zip')]) == 0
    assert len(list(tmp_path.glob('*_share/share.zip'))) == 1
    page = tmp_path / 'document.html'
    page.write_text('<html><img src="missing.png"></html>')
    config.with_suffix('.outputs.json').write_text(json.dumps({'first': {'reference': {'path': 'document.html'}}}))
    response = export(TestClient(create_app(config)), True)
    assert response.status_code == 422
    assert 'missing.png' in response.json()['detail']
