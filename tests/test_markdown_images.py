from pathlib import Path

import pytest
import yaml

from ontolens.content import parse_editorial_source
from ontolens.markdown_images import inspect_images
from test_project import fixture


def test_image_inspection_resolves_paths_and_ignores_code(tmp_path):
    figures = tmp_path / 'figures'
    figures.mkdir()
    (figures / 'my image.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (tmp_path / 'secret.txt').write_text('not an image')
    text = '''---
title: Test
---
![Present](figures/my%20image.svg#detail)
![Same](figures/my%20image.svg#detail)
![Missing](figures/missing.png)
![Remote](https://example.org/image.png)
![Embedded](data:image/png;base64,YQ==)
![Not an image](secret.txt)
![Unsafe](file:///secret.txt)

```markdown
![Code only](not-actually-used.png)
```
'''
    images = inspect_images(parse_editorial_source(text, tmp_path / 'content.md'))
    assert len(images) == 6
    assert images[0].path == figures / 'my image.svg'
    assert not images[0].error
    assert 'nicht gefunden' in images[1].error
    assert images[2].path is None and not images[2].error
    assert images[3].path is None and not images[3].error
    assert images[4].error and images[5].error
    nested = tmp_path / 'docs'
    nested.mkdir()
    assert inspect_images(parse_editorial_source('![Up](../figures/my%20image.svg)', nested / 'content.md'))[0].path == images[0].path


def test_markdown_image_preview_and_check_do_not_write_draft(tmp_path):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from ontolens.web import create_project_app
    config, settings = fixture(tmp_path)
    settings['ontologies'][0]['content'] = 'content.md'
    config.write_text(yaml.safe_dump(settings))
    working = tmp_path / 'content.md'
    working.write_text('# Saved original')
    image = tmp_path / 'diagram.svg'
    image.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect width="12" height="12"/></svg>')
    (tmp_path / 'private.html').write_text('<script>alert(1)</script>')
    client = TestClient(create_project_app(config))
    revision = client.get('/api/project').json()['revision']
    headers = {'X-Ontolens-Write': '1'}
    body = {'revision': revision, 'content': '![Draft](diagram.svg)\n![Missing](absent.jpg)\n![No](private.html)'}
    url = '/api/ontologies/first/markdown'
    assert client.post(url + '/images', json=body).status_code == 403
    assert client.post(url + '/images', json=body | {'revision': 'stale'}, headers=headers).status_code == 409
    result = client.post(url + '/images', json=body, headers=headers)
    assert result.status_code == 200
    images = result.json()['images']
    assert images[0]['preview'].startswith(url + '/images/')
    assert images[1]['error'] and images[1]['preview'] is None
    assert images[2]['error'] and images[2]['preview'] is None
    response = client.get(images[0]['preview'])
    assert response.status_code == 200
    assert response.content == image.read_bytes()
    assert response.headers['content-type'] == 'image/svg+xml'
    assert 'sandbox' in response.headers['content-security-policy']
    assert response.headers['cache-control'] == 'no-store'
    assert client.get(images[0]['preview'].replace('/first/', '/second/')).status_code == 404
    assert client.get(url + '/images/private.html').status_code == 404
    assert client.get(url + '/images/unknown').status_code == 404
    checked = client.post(url + '/check', json=body, headers=headers).json()
    assert checked['issues'] and checked['images'][1]['error']
    assert working.read_text() == '# Saved original'
    image.unlink()
    assert client.get(images[0]['preview']).status_code == 404
    assert client.post(url + '/images', json=body, headers=headers).json()['images'][0]['error']
    working_revision = client.get(url).json()['content_revision']
    saved = client.put(url, json=body | {'content_revision': working_revision}, headers=headers)
    assert saved.status_code == 200  # Missing pictures must not block saving text.
    client.post(url + '/detach', json={'revision': revision}, headers=headers)
    assert client.get(images[0]['preview']).status_code == 404
    assert client.post(url + '/images', json=body | {'revision': client.get('/api/project').json()['revision']}, headers=headers).status_code == 422


def test_mounted_project_image_urls(tmp_path):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from ontolens.web import create_app
    config, settings = fixture(tmp_path)
    settings['ontologies'][0]['content'] = 'content.md'
    config.write_text(yaml.safe_dump(settings))
    (tmp_path / 'content.md').write_text('# Test')
    (tmp_path / 'diagram.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    client = TestClient(create_app(config))
    base = client.get('/api/projects').json()['projects'][0]['base']
    revision = client.get(base + '/api/project').json()['revision']
    result = client.post(base + '/api/ontologies/first/markdown/images',
                         headers={'X-Ontolens-Write': '1'},
                         json={'revision': revision, 'content': '![Test](diagram.svg)'})
    preview = result.json()['images'][0]['preview']
    assert preview.startswith(base + '/api/')
    assert client.get(preview).status_code == 200
