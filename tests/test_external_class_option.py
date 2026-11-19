import json
import re
from pathlib import Path

import pytest
import yaml

from ontolens.cli import main
from ontolens.project import build_project, load_project
from ontolens.render import generate
from test_content import ONTOLOGY


ISOLATED = 'https://external.example/Isolated'
ENDPOINT = 'https://external.example/Endpoint'
SOURCE = ONTOLOGY + f'''
<{ISOLATED}> a owl:Class .
<{ENDPOINT}> a owl:Class .
ex:external a owl:DatatypeProperty ; rdfs:domain <{ENDPOINT}> ; rdfs:range rdfs:Literal .
'''


def assert_option(path, enabled):
    html = Path(path).read_text(encoding='utf-8')
    graph = json.loads(re.search(r'window\.ontolensVisualization = (.*);', html)[1])
    ids = {node['data']['id'] for node in graph['elements']['nodes']}
    assert (ISOLATED in ids) == enabled
    assert ENDPOINT in ids


def setup_source(tmp_path):
    source = tmp_path / 'ontology.ttl'
    source.write_text(SOURCE, encoding='utf-8')
    (tmp_path / 'content.md').write_text('# Introduction\n\nExample.', encoding='utf-8')
    return source


@pytest.mark.parametrize('enabled', [True, False])
@pytest.mark.parametrize('theme', ['light', 'dark', 'both'])
def test_generator_option_in_combined_and_theme_variants(tmp_path, enabled, theme):
    source = setup_source(tmp_path)
    output = generate(source, tmp_path / 'combined.html', content_path=tmp_path / 'content.md',
                      include_external_classes=enabled, theme=theme)
    assert_option(output, enabled)
    if theme == 'both':
        assert_option(output.parent.parent / 'dark' / output.name, enabled)


def test_cli_flag_defaults_and_project_precedence(tmp_path):
    source = setup_source(tmp_path)
    for name, flags, enabled in [('default', [], False), ('on', ['--include-external-classes'], True),
                                 ('off', ['--no-include-external-classes'], False)]:
        assert main([str(source), '-o', str(tmp_path / f'{name}.html'), *flags]) == 0
        assert_option(next(tmp_path.rglob(f'{name}.html')), enabled)
    config = tmp_path / 'project.yaml'
    config.write_text(yaml.safe_dump({'name': 'test', 'output': 'output',
        'defaults': {'include_external_classes': True},
        'ontologies': [{'id': 'first', 'input': source.name},
                       {'id': 'second', 'input': source.name, 'include_external_classes': False}],
        'portal': {'enabled': True}}), encoding='utf-8')
    built = build_project(load_project(config))
    assert built.portal.is_file()
    assert_option(built.pages[0], True)
    assert_option(built.pages[1], False)
    for flag, enabled in [('--include-external-classes', True), ('--no-include-external-classes', False)]:
        folder = tmp_path / flag.lstrip('-')
        assert main(['build', str(config), '--output', str(folder), flag]) == 0
        for path in folder.rglob('first.html'):
            assert_option(path, enabled)
        for path in folder.rglob('second.html'):
            assert_option(path, enabled)


def test_web_setting_persists_and_controls_both_html_exports(tmp_path):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from ontolens.web import create_app

    source = setup_source(tmp_path)
    config = tmp_path / 'project.yaml'
    config.write_text(yaml.safe_dump({'ontologies': [
        {'id': 'test', 'input': source.name, 'content': 'content.md'}]}), encoding='utf-8')
    client = TestClient(create_app(config))
    headers = {'X-Ontolens-Write': '1'}
    for enabled in (True, False):
        revision = client.get('/api/project').json()['revision']
        response = client.patch('/api/ontologies/test/settings', headers=headers, json={
            'revision': revision, 'quality_report': False, 'recommendations': False,
            'custom_annotations': False, 'check_content': False, 'include_external_classes': enabled,
        })
        assert response.status_code == 200, response.text
        revision = response.json()['revision']
        assert load_project(config).ontologies[0].options['include_external_classes'] is enabled
        for kind in ('reference', 'combined'):
            if not enabled:
                detached = client.put(f'/api/ontologies/test/html/{kind}', headers=headers,
                                      json={'revision': revision, 'path': None})
                assert detached.status_code == 200, detached.text
            exported = client.post('/api/ontologies/test/export', headers=headers,
                                   json={'revision': revision, 'kind': kind})
            assert exported.status_code == 200, exported.text
            assert_option(exported.json()['path'], enabled)
        reopened = TestClient(create_app(config))
        assert reopened.get('/api/project').json()['ontologies'][0]['options']['include_external_classes'] is enabled
