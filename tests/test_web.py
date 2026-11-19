import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException
from ontolens.web import create_app
from ontolens.web import SettingsUpdate
from ontolens.web import PathUpdate, TemplateRequest, ExportRequest, MarkdownUpdate, RevisionRequest, MarkdownCheckRequest, HtmlAssignment
from test_project import fixture
from ontolens.web import NewProject


def endpoint(app, path):
    routes = [route for route in app.routes if route.path == path]
    return next((route.endpoint for route in routes if 'GET' in route.methods), routes[0].endpoint)


def test_web_project_uses_shared_configuration(tmp_path):
    path, _ = fixture(tmp_path)
    app = create_app(path)
    project = endpoint(app, "/api/project")()
    assert project["name"] == "test-project"
    assert project["notices"] == []
    assert project["ontologies"][0]["options"]["quality_report"] is True
    assert endpoint(app, "/api/ontologies/{ontology_id}/markdown")("first") == {"content": None}
    with pytest.raises(HTTPException) as error:
        endpoint(app, "/api/ontologies/{ontology_id}/markdown")("unknown")
    assert error.value.status_code == 404


def test_missing_config_is_reported(tmp_path):
    app = create_app(tmp_path / "missing.yaml")
    with pytest.raises(HTTPException) as error:
        endpoint(app, "/api/project")()
    assert error.value.status_code == 422


def test_project_picker_isolation_and_persistence(tmp_path, monkeypatch):
    first = tmp_path / 'first'
    second = tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    one, _ = fixture(first)
    two, _ = fixture(second)
    app = create_app(one)
    monkeypatch.setattr('ontolens.web.choose_local_path', lambda *args: str(two))
    open_project = endpoint(app, '/api/projects/open')
    with pytest.raises(HTTPException) as forbidden:
        open_project(None)
    assert forbidden.value.status_code == 403
    opened = open_project('1')['project']
    assert len(endpoint(app, '/api/projects')()['projects']) == 2
    mounted = next(route.app for route in app.routes if route.path == opened['base'])
    assert endpoint(mounted, '/api/project')()['config'] == str(two)
    assert endpoint(app, '/api/project')()['config'] == str(one)
    project = endpoint(mounted, '/api/project')()
    output = endpoint(mounted, '/api/ontologies/{ontology_id}/export')('first', ExportRequest(revision=project['revision'], kind='reference'), '1')
    assert output['preview'].startswith(opened['base'] + '/api/')
    assert endpoint(app, '/api/project')()['ontologies'][0]['html']['reference'] is None
    restarted = create_app(one)
    assert len(endpoint(restarted, '/api/projects')()['projects']) == 2
    monkeypatch.setattr('ontolens.web.choose_local_path', lambda *args: None)
    assert endpoint(restarted, '/api/projects/open')('1') == {'project': None}


def test_new_project_with_multiple_files(tmp_path, monkeypatch):
    from pathlib import Path
    from ontolens.project import load_project
    first = tmp_path / 'one'
    second = tmp_path / 'two'
    first.mkdir()
    second.mkdir()
    config, _ = fixture(first)
    fixture(second)
    sources = [first / 'ontology.ttl', second / 'ontology.ttl']
    original = [source.read_bytes() for source in sources]
    app = create_app(config)
    create = next(r.endpoint for r in app.routes if r.path == '/api/projects' and 'POST' in r.methods)
    request = NewProject(name='Meine Ontologien', directory=str(tmp_path), ontologies=[str(p) for p in sources] + [str(sources[0])])
    with pytest.raises(HTTPException) as forbidden:
        create(request, None)
    assert forbidden.value.status_code == 403
    result = create(request, '1')['project']
    created = load_project(Path(result['path']))
    assert created.name == 'Meine Ontologien'
    assert len(created.ontologies) == 2
    assert len({o.id for o in created.ontologies}) == 2
    assert [o.input for o in created.ontologies] == sources
    assert [source.read_bytes() for source in sources] == original
    with pytest.raises(HTTPException) as existing:
        create(request, '1')
    assert existing.value.status_code == 409
    assert len(endpoint(create_app(config), '/api/projects')()['projects']) == 2
    with pytest.raises(HTTPException) as empty:
        create(NewProject(name='Empty', directory=str(tmp_path), ontologies=[]), '1')
    assert empty.value.status_code == 422
    bad = tmp_path / 'invalid.ttl'
    bad.write_text('not a turtle file', encoding='utf-8')
    with pytest.raises(HTTPException) as invalid:
        create(NewProject(name='Invalid', directory=str(tmp_path), ontologies=[str(bad)]), '1')
    assert invalid.value.status_code == 422
    assert not (tmp_path / 'invalid-project').exists()
    monkeypatch.setattr('ontolens.web.choose_local_path', lambda *args: [str(p) for p in sources])
    assert endpoint(app, '/api/projects/dialog/{kind}')('ontologies', '1')['paths'] == [str(p) for p in sources]


def test_copied_project_survives_move(tmp_path):
    import shutil
    from pathlib import Path
    from ontolens.project import load_project
    sources = tmp_path / 'original'
    sources.mkdir()
    config, _ = fixture(sources)
    (sources / 'figures').mkdir()
    (sources / 'figures/example.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding='utf-8')
    source = sources / 'ontology.ttl'
    with source.open('a', encoding='utf-8') as stream:
        stream.write('\n<https://example.org/ontology> rdfs:comment "![Diagram](figures/example.svg)"@en .\n')
    original = source.read_bytes()
    app = create_app(config)
    create = next(r.endpoint for r in app.routes if r.path == '/api/projects' and 'POST' in r.methods)
    result = create(NewProject(name='Portable', directory=str(tmp_path), ontologies=[str(source)], copy_sources=True), '1')['project']
    project_path = Path(result['path'])
    assert 'input: sources/' in project_path.read_text(encoding='utf-8')
    child = create_app(project_path)
    revision = endpoint(child, '/api/project')()['revision']
    endpoint(child, '/api/ontologies/{ontology_id}/template')('ontology-ontology', TemplateRequest(revision=revision), '1')
    revision = endpoint(child, '/api/project')()['revision']
    endpoint(child, '/api/ontologies/{ontology_id}/export')('ontology-ontology', ExportRequest(revision=revision, kind='reference'), '1')
    assert source.read_bytes() == original
    moved = tmp_path / 'moved'
    shutil.copytree(project_path.parent, moved)
    shutil.rmtree(sources)
    shutil.rmtree(project_path.parent)
    loaded = load_project(moved / project_path.name)
    assert loaded.ontologies[0].input.is_relative_to(moved)
    assert loaded.ontologies[0].content.is_file()
    reopened = create_app(moved / project_path.name)
    linked = endpoint(reopened, '/api/project')()['ontologies'][0]['html']['reference']
    assert linked['available']
    assert Path(linked['path']).is_relative_to(moved)
    from ontolens.render import generate
    output = generate(loaded.ontologies[0].input, moved / 'new.html')
    assert list((output.parent / 'img').glob('*.svg'))


def test_settings_change_generated_html(tmp_path):
    from pathlib import Path
    from bs4 import BeautifulSoup
    path, _ = fixture(tmp_path)
    source = tmp_path / 'ontology.ttl'
    with source.open('a', encoding='utf-8') as stream:
        stream.write('\n<https://example.org/ontology#custom> a <http://www.w3.org/2002/07/owl#AnnotationProperty> .\n'
                     '<https://example.org/ontology#TestClass> a <http://www.w3.org/2002/07/owl#Class> ; '
                     '<https://example.org/ontology#custom> "UNIQUE-CUSTOM-ANNOTATION" .\n')
    app = create_app(path)
    revision = endpoint(app, '/api/project')()['revision']
    for enabled in (True, False):
        endpoint(app, '/api/ontologies/{ontology_id}/html/{kind}')('first', 'reference', HtmlAssignment(revision=revision), '1')
        settings = endpoint(app, '/api/ontologies/{ontology_id}/settings')('first',
            SettingsUpdate(revision=revision, quality_report=enabled, recommendations=enabled,
                           custom_annotations=enabled, check_content=False), '1')
        revision = settings['revision']
        result = endpoint(app, '/api/ontologies/{ontology_id}/export')('first',
            ExportRequest(revision=revision, kind='reference'), '1')
        html = Path(result['path']).read_text(encoding='utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        assert bool(soup.select_one('#quality-report')) == enabled
        assert bool(soup.select_one('.missing-mandatory')) == enabled
        assert ('UNIQUE-CUSTOM-ANNOTATION' in html) == enabled


def test_html_theme_setting_and_export(tmp_path):
    from pathlib import Path
    from bs4 import BeautifulSoup
    path, _ = fixture(tmp_path)
    app = create_app(path)
    revision = endpoint(app, '/api/project')()['revision']
    result = endpoint(app, '/api/ontologies/{ontology_id}/settings')('first',
        SettingsUpdate(revision=revision, quality_report=False, recommendations=False,
                       custom_annotations=False, check_content=False, theme='dark'), '1')
    assert result['options']['theme'] == 'dark'
    exported = endpoint(app, '/api/ontologies/{ontology_id}/export')('first',
        ExportRequest(revision=result['revision'], kind='reference'), '1')
    soup = BeautifulSoup(Path(exported['path']).read_text(encoding='utf-8'), 'html.parser')
    assert soup.html['data-theme'] == 'dark'
    assert soup.select_one('#document-dark-mode') is None
    from ontolens.render import generate
    md = tmp_path / 'content.md'
    md.write_text('# Introduction\nText.', encoding='utf-8')
    combined = generate(tmp_path / 'ontology.ttl', tmp_path / 'combined.html', content_path=md, theme='dark')
    soup = BeautifulSoup(combined.read_text(encoding='utf-8'), 'html.parser')
    assert soup.html['data-theme'] == 'dark'
    assert soup.select_one('.document-options #document-dark-mode') is None
    light = generate(tmp_path / 'ontology.ttl', tmp_path / 'light.html')
    assert 'data-theme="light"' in light.read_text(encoding='utf-8')


def test_overview_reports_missing_ontology_figure(tmp_path, monkeypatch):
    from types import SimpleNamespace
    path, _ = fixture(tmp_path)
    monkeypatch.setattr("ontolens.web.load_ontology", lambda *args, **kwargs: SimpleNamespace(
        hero_figures=[SimpleNamespace(src="figures/missing.svg"), SimpleNamespace(src="https://example.org/image.svg")]))
    result = endpoint(create_app(path), "/api/project")()
    assert len(result["notices"]) == 2
    assert result["notices"][0] == {"ontology": "first", "message": "Abbildung fehlt: figures/missing.svg"}


def test_settings_write_and_conflict(tmp_path):
    import yaml
    path, _ = fixture(tmp_path)
    path.write_text('# Keep this comment\n' + path.read_text(), encoding='utf-8')
    app = create_app(path)
    before = endpoint(app, '/api/project')()
    change = SettingsUpdate(revision=before['revision'], quality_report=False,
                            recommendations=True, custom_annotations=False, check_content=False)
    save = endpoint(app, '/api/ontologies/{ontology_id}/settings')
    with pytest.raises(HTTPException) as forbidden:
        save('first', change, None)
    assert forbidden.value.status_code == 403
    save('first', change, '1')
    assert '# Keep this comment' in path.read_text()
    result = yaml.safe_load(path.read_text())
    assert result['defaults']['quality_report'] is True
    assert result['ontologies'][0]['quality_report'] is False
    assert result['ontologies'][0]['recommendations'] is True
    assert result['ontologies'][1]['quality_report'] is False
    with pytest.raises(HTTPException) as conflict:
        save('first', change, '1')
    assert conflict.value.status_code == 409


def test_settings_reject_missing_markdown(tmp_path):
    path, _ = fixture(tmp_path)
    app = create_app(path)
    before = path.read_bytes()
    change = SettingsUpdate(revision=endpoint(app, '/api/project')()['revision'], quality_report=False,
                            recommendations=False, custom_annotations=False, check_content=True)
    with pytest.raises(HTTPException) as error:
        endpoint(app, '/api/ontologies/{ontology_id}/settings')('first', change, '1')
    assert error.value.status_code == 422
    assert before == path.read_bytes()


def test_generate_template_assigns_and_prevents_overwrite(tmp_path):
    path, _ = fixture(tmp_path)
    app = create_app(path)
    before = endpoint(app, '/api/project')()
    result = endpoint(app, '/api/ontologies/{ontology_id}/template')('first', TemplateRequest(revision=before['revision'], profile='compact'), '1')
    from pathlib import Path
    generated = Path(result['ontologies'][0]['content'])
    assert generated.is_relative_to(tmp_path / 'out')
    text = generated.read_text(encoding='utf-8')
    assert 'profile: compact' in text
    assert 'chapter introduction' in text
    with pytest.raises(HTTPException) as error:
        endpoint(app, '/api/ontologies/{ontology_id}/template')('first', TemplateRequest(revision=result['revision']), '1')
    assert error.value.status_code == 409
    assert generated.read_text(encoding='utf-8') == text


def test_manual_markdown_and_output_assignment(tmp_path):
    path, _ = fixture(tmp_path)
    app = create_app(path)
    markdown = tmp_path / 'manual.md'
    markdown.write_text('# Text', encoding='utf-8')
    revision = endpoint(app, '/api/project')()['revision']
    save = endpoint(app, '/api/ontologies/{ontology_id}/path')
    result = save('first', PathUpdate(revision=revision, kind='content', path=str(markdown)), '1')
    assert result['ontologies'][0]['content'] == str(markdown)
    result = save('first', PathUpdate(revision=result['revision'], kind='output', path=str(tmp_path)), '1')
    assert result['output'] == str(tmp_path)
    assert result['ontologies'][1]['content'] is None


def test_native_picker_cancel_and_header(tmp_path, monkeypatch):
    path, _ = fixture(tmp_path)
    monkeypatch.setattr('ontolens.web.choose_local_path', lambda *args: None)
    choose = endpoint(create_app(path), '/api/dialog/{kind}')
    assert choose('input', '1') == {'path': None}
    with pytest.raises(HTTPException) as error:
        choose('output', None)
    assert error.value.status_code == 403


def test_exports_and_registered_files(tmp_path):
    from pathlib import Path
    from zipfile import ZipFile
    path, _ = fixture(tmp_path)
    app = create_app(path)
    revision = endpoint(app, '/api/project')()['revision']
    export = endpoint(app, '/api/ontologies/{ontology_id}/export')
    request = ExportRequest(revision=revision, kind='reference')
    with pytest.raises(HTTPException) as forbidden:
        export('first', request, None)
    assert forbidden.value.status_code == 403
    with pytest.raises(HTTPException) as missing:
        export('first', ExportRequest(revision=revision, kind='combined'), '1')
    assert missing.value.status_code == 422
    result = export('first', request, '1')
    assert any('metadata' in notice.lower() for notice in result['notices'])
    without_quality = export('second', request, '1')
    assert without_quality['notices'] == []
    page = Path(result['path'])
    assert page.is_file()
    token = result['download'].split('/')[3]
    response = endpoint(app, '/api/exports/{token}/download')(token)
    with ZipFile(response.path) as archive:
        assert page.name in archive.namelist()
        assert any(name.startswith('downloads/') for name in archive.namelist())
    preview = endpoint(app, '/api/exports/{token}/files/{filename:path}')
    assert Path(preview(token, page.name).path) == page
    with pytest.raises(HTTPException) as traversal:
        preview(token, '../../project.yaml')
    assert traversal.value.status_code == 404
    markdown = tmp_path / 'editorial.md'
    markdown.write_text('# Editorial test\n\nUnique editorial paragraph.', encoding='utf-8')
    updated = endpoint(app, '/api/ontologies/{ontology_id}/path')(
        'first', PathUpdate(revision=revision, kind='content', path=str(markdown)), '1')
    with pytest.raises(HTTPException) as stale:
        export('first', request, '1')
    assert stale.value.status_code == 409
    revision = updated['revision']
    combined = export('first', ExportRequest(revision=revision, kind='combined'), '1')
    assert 'Unique editorial paragraph.' in Path(combined['path']).read_text(encoding='utf-8')
    assert 'Unique editorial paragraph.' not in page.read_text(encoding='utf-8')
    copied = export('first', ExportRequest(revision=revision, kind='markdown'), '1')
    assert Path(copied['path']) == markdown
    assert Path(copied['path']).read_bytes() == markdown.read_bytes()


def test_markdown_working_file_save_download_and_detach(tmp_path):
    from pathlib import Path
    path, _ = fixture(tmp_path)
    app = create_app(path)
    current = endpoint(app, '/api/project')()
    current = endpoint(app, '/api/ontologies/{ontology_id}/template')(
        'first', TemplateRequest(revision=current['revision']), '1')
    working = Path(current['ontologies'][0]['content'])
    read = endpoint(app, '/api/ontologies/{ontology_id}/markdown')
    # GET and PUT share a route path.
    save = next(r.endpoint for r in app.routes if r.path == '/api/ontologies/{ontology_id}/markdown' and 'PUT' in r.methods)
    read = next(r.endpoint for r in app.routes if r.path == '/api/ontologies/{ontology_id}/markdown' and 'GET' in r.methods)
    before = read('first')
    request = MarkdownUpdate(revision=current['revision'], content_revision=before['content_revision'], content='# Updated\n')
    with pytest.raises(HTTPException) as forbidden:
        save('first', request, None)
    assert forbidden.value.status_code == 403
    result = save('first', request, '1')
    assert result['content'] == '# Updated\n'
    assert working.read_text(encoding='utf-8') == '# Updated\n'
    with pytest.raises(HTTPException) as stale:
        save('first', request, '1')
    assert stale.value.status_code == 409
    files = set(tmp_path.rglob('*'))
    download = endpoint(app, '/api/ontologies/{ontology_id}/markdown/download')('first')
    assert Path(download.path) == working
    assert set(tmp_path.rglob('*')) == files
    detached = endpoint(app, '/api/ontologies/{ontology_id}/markdown/detach')(
        'first', RevisionRequest(revision=current['revision']), '1')
    assert detached['ontologies'][0]['content'] is None
    assert detached['ontologies'][0]['options']['check_content'] is False
    assert working.is_file()
    with pytest.raises(HTTPException) as missing:
        endpoint(app, '/api/ontologies/{ontology_id}/markdown/download')('first')
    assert missing.value.status_code == 404
    with pytest.raises(HTTPException) as combined:
        endpoint(app, '/api/ontologies/{ontology_id}/export')('first', ExportRequest(revision=detached['revision'], kind='combined'), '1')
    assert combined.value.status_code == 422
    recreated = endpoint(app, '/api/ontologies/{ontology_id}/template')(
        'first', TemplateRequest(revision=detached['revision'], profile='compact'), '1')
    assert Path(recreated['ontologies'][0]['content']) != working
    assert working.read_text(encoding='utf-8') == '# Updated\n'


def test_check_unsaved_markdown_without_writes(tmp_path):
    path, _ = fixture(tmp_path)
    app = create_app(path)
    current = endpoint(app, '/api/project')()
    check = endpoint(app, '/api/ontologies/{ontology_id}/markdown/check')
    request = MarkdownCheckRequest(revision=current['revision'], content='# Draft')
    with pytest.raises(HTTPException) as missing:
        check('first', request, '1')
    assert missing.value.status_code == 422
    current = endpoint(app, '/api/ontologies/{ontology_id}/template')(
        'first', TemplateRequest(revision=current['revision'], profile='compact'), '1')
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    text = '---\nlanguage: de\nprofile: compact\n---\n# Einleitung\n\nEin Inhalt.\n'
    request = MarkdownCheckRequest(revision=current['revision'], content=text)
    with pytest.raises(HTTPException) as forbidden:
        check('first', request, None)
    assert forbidden.value.status_code == 403
    result = check('first', request, '1')
    assert len(result['issues']) == 3
    assert all(issue['chapter'] != 'introduction' for issue in result['issues'])
    complete = text + '\n# Umfang und Anforderungen\nText\n# Konzeptionelles Modell\nText\n# Anwendung und Beispiele\nText\n'
    assert check('first', MarkdownCheckRequest(revision=current['revision'], content=complete), '1') == {'issues': [], 'images': []}
    with pytest.raises(HTTPException) as invalid:
        check('first', MarkdownCheckRequest(revision=current['revision'], content='---\nprofile: invalid\n---\n'), '1')
    assert invalid.value.status_code == 422
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_html_assignment_restart_assets_and_detach(tmp_path):
    from pathlib import Path
    path, _ = fixture(tmp_path)
    app = create_app(path)
    revision = endpoint(app, '/api/project')()['revision']
    output = endpoint(app, '/api/ontologies/{ontology_id}/export')('first', ExportRequest(revision=revision, kind='reference'), '1')
    restarted = create_app(path)
    token = output['download'].split('/')[3]
    assert Path(endpoint(restarted, '/api/exports/{token}/download')(token).path).is_file()
    linked = endpoint(restarted, '/api/project')()['ontologies'][0]['html']['reference']
    assert linked['path'] == output['path']
    assert linked['report_available'] is True
    with pytest.raises(HTTPException) as assigned:
        endpoint(restarted, '/api/ontologies/{ontology_id}/export')('first', ExportRequest(revision=revision, kind='reference'), '1')
    assert assigned.value.status_code == 409
    page = tmp_path / 'existing.html'
    page.write_text('<html><img src="img/test.svg"></html>', encoding='utf-8')
    (tmp_path / 'img').mkdir()
    image = tmp_path / 'img/test.svg'
    image.write_text('<svg/>', encoding='utf-8')
    assign = endpoint(restarted, '/api/ontologies/{ontology_id}/html/{kind}')
    request = HtmlAssignment(revision=revision, path=str(page))
    with pytest.raises(HTTPException) as forbidden:
        assign('first', 'combined', request, None)
    assert forbidden.value.status_code == 403
    result = assign('first', 'combined', request, '1')
    combined = result['ontologies'][0]['html']['combined']
    assert combined['report_available'] is False
    token2 = combined['download'].split('/')[3]
    preview = endpoint(create_app(path), '/api/exports/{token}/files/{filename:path}')
    assert Path(preview(token2, 'img/test.svg').path) == image
    for denied in ('../existing.html', 'project.yaml', 'ontology.ttl'):
        with pytest.raises(HTTPException) as blocked:
            preview(token2, denied)
        assert blocked.value.status_code == 404
    result = assign('first', 'reference', HtmlAssignment(revision=revision), '1')
    assert result['ontologies'][0]['html']['reference'] is None
    assert result['ontologies'][0]['html']['combined'] is not None
    assert Path(output['path']).is_file()
    with pytest.raises(HTTPException):
        endpoint(restarted, '/api/exports/{token}/download')(token)
    original = page.read_bytes()
    assign('first', 'combined', HtmlAssignment(revision=revision), '1')
    assert page.read_bytes() == original
    assign('first', 'reference', request, '1')
    page.unlink()
    assert endpoint(create_app(path), '/api/project')()['ontologies'][0]['html']['reference']['available'] is False
    assign('first', 'reference', HtmlAssignment(revision=revision), '1')


def test_legacy_html_report_availability(tmp_path):
    import json
    config, _ = fixture(tmp_path)
    page = tmp_path / 'legacy.html'
    page.write_text('<html></html>')
    registry = config.with_suffix('.outputs.json')
    app = create_app(config)
    record = {'path': 'legacy.html', 'notices': ['Saved warning']}
    registry.write_text(json.dumps({'first': {'reference': record}}))
    linked = endpoint(app, '/api/project')()['ontologies'][0]['html']['reference']
    assert linked['report_available'] is True
    assert linked['notices'] == ['Saved warning']
    record.update(notices=[], archive='missing-archive.zip')
    registry.write_text(json.dumps({'first': {'reference': record}}))
    assert endpoint(app, '/api/project')()['ontologies'][0]['html']['reference']['report_available'] is True
    del record['archive']
    registry.write_text(json.dumps({'first': {'reference': record}}))
    assert endpoint(app, '/api/project')()['ontologies'][0]['html']['reference']['report_available'] is False
