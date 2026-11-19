"""Run via `docker compose exec -T ontolens python -` (stdin).

Creates isolated test data under /data, never edits existing projects.
After restarting the service, pass --verify /data/.../manifest.json.
"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import ZipFile

from bs4 import BeautifulSoup

BASE = 'http://127.0.0.1:8000'


def call(path, method='GET', data=None, status=200, raw=False):
    request = Request(BASE + path, method=method,
                      data=json.dumps(data).encode() if data is not None else None,
                      headers={'Content-Type': 'application/json', 'X-Ontolens-Write': '1'})
    try:
        response = urlopen(request, timeout=120)
    except HTTPError as error:
        response = error
    body = response.read()
    assert response.status == status, (method, path, response.status, body[:1000])
    return body if raw else json.loads(body)


def verify_export(result):
    call(result['preview'], raw=True)
    for theme, variant in result.get('variants', {}).items():
        html = call(variant['preview'], raw=True)
        soup = BeautifulSoup(html, 'html.parser')
        assert soup.html['data-theme'] == theme
        assert soup.select_one('#document-dark-mode') is None
        # Check local document, image, download and portal navigation links.
        for tag in soup.select('img[src], a[href]'):
            ref = tag.get('src', tag.get('href'))
            if not ref or ref.startswith(('#', 'http:', 'https:', 'mailto:', 'data:')):
                continue
            call(urljoin(variant['preview'], ref), raw=True)
    if result['downloadLabel'].startswith('ZIP'):
        with ZipFile(io.BytesIO(call(result['download'], raw=True))) as archive:
            assert archive.testzip() is None
            for theme in result.get('variants', {}):
                assert any(name.startswith(theme + '/') and name.endswith('.html') for name in archive.namelist())


def verify_pdf(manifest):
    saved = json.loads(Path(manifest).read_text())
    project = call(saved['base'] + '/api/project')
    identity = project['ontologies'][0]['id']
    request = {'revision': project['revision'], 'documents': [{'ontology': identity, 'kind': 'reference'}]}
    single = call(saved['base'] + '/api/project/pdf', 'POST', request, raw=True)
    assert single.startswith(b'%PDF-') and len(single) > 1000
    request.update(paper='A3', figures=False, graph=True)
    request['documents'].append({'ontology': identity, 'kind': 'combined'})
    multiple = call(saved['base'] + '/api/project/pdf', 'POST', request, raw=True)
    with ZipFile(io.BytesIO(multiple)) as archive:
        assert len(archive.namelist()) == 2
        assert archive.testzip() is None
        assert all(archive.read(name).startswith(b'%PDF-') for name in archive.namelist())
    print('PASS: real Docker PDF renderer, single A4 PDF, A3 batch ZIP, combined HTML and static graph', flush=True)


def verify_archive(manifest):
    from ontolens.project import load_project, build_project
    saved = json.loads(Path(manifest).read_text())
    project = call(saved['base'] + '/api/project')
    for included in (False, True):
        data = call(saved['base'] + '/api/project/archive', 'POST',
                    {'revision': project['revision'], 'include_outputs': included}, raw=True)
        with tempfile.TemporaryDirectory(prefix='ontolens-unpack-test-') as directory:
            with ZipFile(io.BytesIO(data)) as archive:
                assert archive.testzip() is None
                assert ('project/ontolens.project.outputs.json' in archive.namelist()) == included
                archive.extractall(directory)
            config = Path(directory) / 'project/ontolens.project.yaml'
            copied = load_project(config)
            assert all(item.input.is_relative_to(config.parent) for item in copied.ontologies)
            assert build_project(copied).pages
    print('PASS: project ZIP with/without outputs, unpack and rebuild in Docker; no new registered project', flush=True)


def verify(manifest):
    saved = json.loads(Path(manifest).read_text())
    project = call(saved['base'] + '/api/project')
    assert project['name'] == saved['name']
    assert Path(project['ontologies'][0]['content']).is_file()
    assert 'Docker smoke editorial text.' in call(saved['base'] + '/api/ontologies/' + project['ontologies'][0]['id'] + '/markdown')['content']
    for result in saved['outputs']:
        verify_export(result)
    assert call(saved['base'] + '/api/project')['portal']['result']['available']
    print('PASS: persisted project, Markdown, both HTML variants, ZIPs and portal after restart', flush=True)


def examples(folder):
    folder = Path(folder)
    request = {'name': 'Docker examples ' + uuid4().hex[:6], 'directory': str(folder.parent),
               'ontologies': [str(folder / name / (name + '.ttl')) for name in ('loin', 'tempo', 'isoprops')],
               'copy_sources': False}
    entry = call('/api/projects', 'POST', request)['project']
    base = entry['base']
    project = call(base + '/api/project')
    for item in project['ontologies']:
        settings = call(base + '/api/ontologies/' + item['id'] + '/settings', 'PATCH', {
            'revision': project['revision'], 'quality_report': True, 'recommendations': True,
            'custom_annotations': True, 'check_content': False, 'skip_missing_images': True,
            'show_missing_endpoints': True, 'language': 'de',
        })
        project['revision'] = settings['revision']
    isoprops = next(item for item in project['ontologies'] if item['id'].endswith('isoprops'))
    project = call(base + '/api/ontologies/' + isoprops['id'] + '/path', 'PATCH', {
        'revision': project['revision'], 'kind': 'content', 'path': str(folder / 'isoprops/documentation.de.md'),
    })
    project = call(base + '/api/portal/export', 'POST', {
        'revision': project['revision'], 'title': 'LOIN, TempO & ISOProps (Docker)',
        'ontologies': [item['id'] for item in project['ontologies']], 'theme': 'both',
    })
    result = project['portal']['result']
    verify_export(result)
    for variant in result['variants'].values():
        soup = BeautifulSoup(call(variant['preview'], raw=True), 'html.parser')
        for link in soup.select('h2 a'):
            document_url = urljoin(variant['preview'], link['href'])
            document = BeautifulSoup(call(document_url, raw=True), 'html.parser')
            for img in document.select('img[src]'):
                if not img['src'].startswith(('http:', 'https:', 'data:')):
                    call(urljoin(document_url, img['src']), raw=True)
    print('PASS: LOIN, TempO and ISOProps portal, light/dark, Markdown, images and ZIP', flush=True)
    print('PORTAL=' + result['variants']['dark']['preview'], flush=True)


def run():
    assert os.getuid() != 0, 'Runtime must not run as root'
    for _ in range(40):
        try:
            if call('/api/health')['status'] == 'ok':
                break
        except URLError:
            time.sleep(1)
    else:
        raise RuntimeError('API did not become healthy')
    if len(sys.argv) > 1 and sys.argv[1] == '--pdf':
        verify_pdf(sys.argv[2])
        return
    if len(sys.argv) > 1 and sys.argv[1] == '--archive':
        verify_archive(sys.argv[2])
        return
    if len(sys.argv) > 1 and sys.argv[1] == '--verify':
        verify(sys.argv[2])
        return
    if len(sys.argv) > 1 and sys.argv[1] == '--examples':
        examples(sys.argv[2])
        return
    html = BeautifulSoup(call('/', raw=True), 'html.parser')
    for asset in html.select('script[src], link[href]'):
        call(asset.get('src', asset.get('href')), raw=True)
    runtime = call('/api/runtime')
    assert runtime['file_browser']
    call('/api/files?' + urlencode({'path': '/etc'}), status=403)
    root = Path(runtime['root']) / ('docker-smoke-' + uuid4().hex[:8])
    root.mkdir()
    source = root / 'test.ttl'
    source.write_text('''@prefix ex: <https://example.org/smoke#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<https://example.org/smoke> a owl:Ontology ; rdfs:label "Docker test" ;
  rdfs:comment "![Diagram](figure.svg)" .
ex:Thing a owl:Class .
ex:hasPart a owl:ObjectProperty ; rdfs:domain ex:Thing .
''', encoding='utf-8')
    (root / 'figure.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>')
    original = source.read_bytes()
    assert any(entry['name'] == 'test.ttl' for entry in call('/api/files?' + urlencode({'path': str(root)}))['entries'])
    name = root.name
    entry = call('/api/projects', 'POST', {'name': name, 'directory': str(root), 'ontologies': [str(source)], 'copy_sources': True})['project']
    base = entry['base']
    project = call(base + '/api/project')
    item = project['ontologies'][0]
    url = base + '/api/ontologies/' + item['id']
    assert Path(item['input']).is_relative_to(Path(entry['path']).parent)
    assert (Path(item['input']).parent / 'img/figure.svg').is_file()
    settings = call(url + '/settings', 'PATCH', {'revision': project['revision'], 'theme': 'both',
        'language': 'de', 'quality_report': True, 'recommendations': True, 'custom_annotations': True,
        'check_content': False, 'show_missing_endpoints': True})
    project = call(url + '/template', 'POST', {'revision': settings['revision'], 'profile': 'standard'})
    md = call(url + '/markdown')
    text = md['content'] + '\nDocker smoke editorial text.\n'
    call(url + '/markdown/check', 'POST', {'revision': project['revision'], 'content': text})
    call(url + '/markdown', 'PUT', {'revision': project['revision'], 'content_revision': md['content_revision'], 'content': text})
    assert call(url + '/markdown/download', raw=True).decode() == text
    outputs = []
    for kind in ('reference', 'combined'):
        result = call(url + '/export', 'POST', {'revision': project['revision'], 'kind': kind})
        verify_export(result)
        outputs.append(result)
    print('PASS: static React assets, file browser, copy with images, Markdown and both HTML exports', flush=True)
    reference = outputs[0]
    call(url + '/html/reference', 'PUT', {'revision': project['revision']})
    call(reference['preview'], status=404)
    reassigned = call(url + '/html/reference', 'PUT', {'revision': project['revision'], 'path': reference['path']})
    outputs[0] = reassigned['ontologies'][0]['html']['reference']
    assert Path(reference['path']).is_file()
    added_source = root / 'second.ttl'
    added_source.write_bytes(original)
    project = call(base + '/api/ontologies', 'POST', {'revision': project['revision'], 'paths': [str(added_source)], 'copy_sources': True})
    added = project['ontologies'][-1]
    project = call(base + '/api/ontologies/' + added['id'] + '/remove', 'POST', {'revision': project['revision']})
    assert Path(added['input']).is_file()
    project = call(base + '/api/portal/export', 'POST', {'revision': project['revision'], 'title': 'Docker smoke portal', 'ontologies': [item['id']], 'theme': 'both'})
    portal = project['portal']['result']
    verify_export(portal)
    outputs.append(portal)
    call(base + '/api/portal/export', 'POST', {'revision': project['revision'], 'title': 'No overwrite', 'ontologies': [item['id']]}, status=409)
    # Use a second workspace to exercise opening an existing config via the browser.
    assert call('/api/projects/open', 'POST', {'path': entry['path']})['project']['base'] == base
    subprocess.run(['ontolens', str(source), '--theme', 'both', '--quality-report', '-o', str(root / 'cli' / 'test.html')], check=True, capture_output=True)
    assert len(list((root / 'cli').rglob('test.html'))) == 2
    assert source.read_bytes() == original
    manifest = root / 'manifest.json'
    manifest.write_text(json.dumps({'base': base, 'name': name, 'outputs': outputs}, indent=2), encoding='utf-8')
    print('PASS: attach/detach, add/remove, portal, ZIP downloads, CLI, original files unchanged', flush=True)
    print('MANIFEST=' + str(manifest), flush=True)


run()
