"""HTTP-level project lifecycle tests; native file dialogs are stubbed only."""
import io
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml

pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from ontolens.project import load_project
from ontolens.web import create_app
from test_project import fixture

HEADERS = {'X-Ontolens-Write': '1'}


def write(client, method, url, data):
    response = client.request(method, url, headers=HEADERS, json=data)
    assert response.status_code == 200, response.text
    return response.json()


def test_portable_project_full_http_workflow(tmp_path):
    original = tmp_path / 'original'
    original.mkdir()
    config, _ = fixture(original)
    source = original / 'ontology.ttl'
    (original / 'figures').mkdir()
    (original / 'figures/detail.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><g id="detail"/></svg>')
    (original / 'figures/overview.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><use href="detail.svg#detail"/></svg>')
    with source.open('a', encoding='utf-8') as stream:
        stream.write('\n<https://example.org/ontology> rdfs:comment "![Overview](figures/overview.svg)"@en .\n')
    original_bytes = source.read_bytes()
    client = TestClient(create_app(config))
    entry = write(client, 'POST', '/api/projects', {
        'name': 'Workflow', 'directory': str(tmp_path), 'ontologies': [str(source)], 'copy_sources': True,
    })['project']
    base = entry['base']
    item_url = base + '/api/ontologies/ontology-ontology'
    project_url = base + '/api/project'
    project = client.get(project_url).json()
    assert project['ontologies'][0]['input'].startswith(str(tmp_path / 'workflow-project'))
    settings = write(client, 'PATCH', item_url + '/settings', {
        'revision': project['revision'], 'quality_report': True, 'recommendations': True,
        'custom_annotations': True, 'check_content': False, 'language': 'de', 'format': 'turtle',
        'theme': 'dark', 'skip_missing_images': True,
    })
    project = write(client, 'POST', item_url + '/template', {'revision': settings['revision'], 'profile': 'compact'})
    markdown_path = Path(project['ontologies'][0]['content'])
    markdown = client.get(item_url + '/markdown').json()
    assert 'language: de' in markdown['content']
    assert 'profile: compact' in markdown['content']
    text = markdown['content'] + '\n\nWorkflow test paragraph.\n'
    write(client, 'POST', item_url + '/markdown/check', {'revision': project['revision'], 'content': text})
    saved = write(client, 'PUT', item_url + '/markdown', {
        'revision': project['revision'], 'content_revision': markdown['content_revision'], 'content': text,
    })
    assert saved['content'] == text
    md_export = write(client, 'POST', item_url + '/export', {'revision': project['revision'], 'kind': 'markdown'})
    assert md_export['download'].startswith(base + '/api/')
    assert client.get(md_export['download']).text == text
    for kind in ('reference', 'combined'):
        exported = write(client, 'POST', item_url + '/export', {'revision': project['revision'], 'kind': kind})
        html = client.get(exported['preview'])
        assert html.status_code == 200
        assert 'data-theme="dark"' in html.text
        assert ('Workflow test paragraph.' in html.text) == (kind == 'combined')
        with ZipFile(io.BytesIO(client.get(exported['download']).content)) as archive:
            assert 'img/overview.svg' in archive.namelist()
            assert 'img/detail.svg' in archive.namelist()
            assert 'downloads/ontology.ttl' in archive.namelist()
        image_url = exported['preview'].rsplit('/', 1)[0] + '/img/detail.svg'
        assert client.get(image_url).status_code == 200
    assert source.read_bytes() == original_bytes
    moved = tmp_path / 'moved'
    shutil.move(str(Path(entry['path']).parent), moved)
    shutil.rmtree(original)
    reopened = TestClient(create_app(moved / 'ontolens.project.yaml'))
    project = reopened.get('/api/project').json()
    item_url = '/api/ontologies/ontology-ontology'
    assert not project['notices']
    assert Path(project['ontologies'][0]['content']).is_file()
    assert reopened.get(project['ontologies'][0]['html']['combined']['preview']).status_code == 200
    project = write(reopened, 'POST', item_url + '/markdown/detach', {'revision': project['revision']})
    assert project['ontologies'][0]['content'] is None
    assert (moved / markdown_path.relative_to(tmp_path / 'workflow-project')).is_file()
    # Published HTML remains available independently of its former editable source.
    linked = project['ontologies'][0]['html']['combined']
    assert reopened.get(linked['preview']).status_code == 200
    project = write(reopened, 'PUT', item_url + '/html/combined', {'revision': project['revision'], 'path': None})
    assert reopened.get(linked['preview']).status_code == 404
    assert reopened.post(item_url + '/export', headers=HEADERS, json={'revision': project['revision'], 'kind': 'combined'}).status_code == 422
    old_html = moved / Path(linked['path']).relative_to(moved)
    project = write(reopened, 'PUT', item_url + '/html/combined', {'revision': project['revision'], 'path': str(old_html)})
    assert project['ontologies'][0]['html']['combined']['available']
    assert reopened.get('/api/ontologies/unknown/markdown').status_code == 404


def test_missing_files_can_be_repaired_in_gui_but_cli_stays_strict(tmp_path):
    config, _ = fixture(tmp_path)
    client = TestClient(create_app(config))
    project = client.get('/api/project').json()
    item_url = '/api/ontologies/first'
    project = write(client, 'POST', item_url + '/template', {'revision': project['revision']})
    Path(project['ontologies'][0]['content']).unlink()
    source = tmp_path / 'ontology.ttl'
    backup = tmp_path / 'restored.ttl'
    source.rename(backup)
    with pytest.raises(ValueError):
        load_project(config)
    restarted = TestClient(create_app(config))
    assert restarted.get('/api/projects').json()['projects'][0]['available']
    project = restarted.get('/api/project').json()
    assert any('Markdown' in n['message'] for n in project['notices'])
    assert restarted.get(item_url + '/markdown').status_code == 422
    project = write(restarted, 'POST', item_url + '/markdown/detach', {'revision': project['revision']})
    for identity in ('first', 'second'):
        project = write(restarted, 'PATCH', f'/api/ontologies/{identity}/path', {
            'revision': project['revision'], 'kind': 'input', 'path': str(backup),
        })
    assert not project['notices']
    assert load_project(config).ontologies[0].input == backup


def test_automatic_options_override_defaults_and_validate_parser(tmp_path):
    config, _ = fixture(tmp_path)
    doc = yaml.safe_load(config.read_text())
    doc['defaults'].update(language='de', format='turtle')
    config.write_text(yaml.safe_dump(doc), encoding='utf-8')
    client = TestClient(create_app(config))
    project = client.get('/api/project').json()
    data = {'revision': project['revision'], 'quality_report': False, 'recommendations': False,
            'custom_annotations': False, 'check_content': False, 'language': None, 'format': None}
    saved = write(client, 'PATCH', '/api/ontologies/first/settings', data)
    loaded = load_project(config)
    assert loaded.ontologies[0].options['language'] is None
    assert loaded.ontologies[0].options['format'] is None
    assert loaded.ontologies[1].options['language'] == 'de'
    data.update(revision=saved['revision'], format='not-a-parser')
    assert client.patch('/api/ontologies/first/settings', headers=HEADERS, json=data).status_code == 422
    data.update(format=None, language='en-GB')
    assert write(client, 'PATCH', '/api/ontologies/first/settings', data)['options']['language'] == 'en-GB'


@pytest.mark.parametrize('identity', ['isoprops', 'loin', 'tempo'])
def test_repository_examples_reference_and_combined(tmp_path, identity):
    root = Path(__file__).resolve().parents[1]
    source = root / 'examples' / identity / f'{identity}.ttl'
    if not source.is_file():
        pytest.skip(f'Optional local example not installed: {identity}')
    config = tmp_path / 'project.yaml'
    config.write_text(yaml.safe_dump({
        'name': identity, 'output': 'build', 'ontologies': [{'id': identity, 'input': str(source),
        'language': 'de', 'quality_report': True, 'recommendations': True,
        'custom_annotations': True, 'skip_missing_images': True}],
    }), encoding='utf-8')
    client = TestClient(create_app(config))
    project = client.get('/api/project').json()
    url = f'/api/ontologies/{identity}'
    project = write(client, 'POST', url + '/template', {'revision': project['revision'], 'profile': 'standard'})
    for kind in ('reference', 'combined'):
        result = write(client, 'POST', url + '/export', {'revision': project['revision'], 'kind': kind})
        assert client.get(result['preview']).status_code == 200
        assert client.get(result['download']).status_code == 200
    restarted = TestClient(create_app(config))
    for result in restarted.get('/api/project').json()['ontologies'][0]['html'].values():
        assert result['available']
        assert restarted.get(result['preview']).status_code == 200


def test_malformed_source_export_is_actionable_error(tmp_path):
    config, _ = fixture(tmp_path)
    client = TestClient(create_app(config))
    project = client.get('/api/project').json()
    (tmp_path / 'ontology.ttl').write_text('broken turtle !')
    response = client.post('/api/ontologies/first/export', headers=HEADERS,
                           json={'revision': project['revision'], 'kind': 'reference'})
    assert response.status_code == 422
    assert 'Export fehlgeschlagen' in response.json()['detail']
