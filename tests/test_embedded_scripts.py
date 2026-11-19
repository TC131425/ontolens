import json
from pathlib import Path
import shutil
import subprocess

from bs4 import BeautifulSoup
import pytest

from ontolens.assets import inline_script, inline_style
from ontolens.render import generate
from test_content import CONTENT, ONTOLOGY


LIBRARIES = ('cytoscape', 'layout-base', 'cose-base', 'cytoscape-fcose')


@pytest.mark.parametrize('theme', ['light', 'dark', 'both'])
@pytest.mark.parametrize('combined', [False, True])
def test_embedded_scripts_licenses_and_separate_images(tmp_path, theme, combined):
    source = tmp_path / 'ontology.ttl'
    source.write_text(ONTOLOGY + '\n<https://example.org/ontology> '
                      'rdfs:comment "![Graph](figure.svg)" .', encoding='utf-8')
    figure = tmp_path / 'figure.svg'
    figure.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"/>', encoding='utf-8')
    content = tmp_path / 'chapters.md'
    content.write_text(CONTENT, encoding='utf-8')
    output = generate(source, tmp_path / 'out.html', theme=theme, content_path=content if combined else None)
    pages = [output, output.parent.parent / 'dark' / output.name] if theme == 'both' else [output]
    static = Path(__file__).parents[1] / 'src/ontolens/static'
    for page in pages:
        soup = BeautifulSoup(page.read_text(encoding='utf-8'), 'html.parser')
        assert not soup.select('script[src]')
        assert not (page.parent / 'assets').exists()
        assert (page.parent / 'img/figure.svg').read_bytes() == figure.read_bytes()
        assert soup.select_one('img[src="img/figure.svg"]')
        assert (page.parent / 'downloads/ontology.ttl').read_bytes() == source.read_bytes()
        for library in LIBRARIES:
            name = library + ('.min' if library == 'cytoscape' else '') + '.js'
            script = soup.select_one(f'script[data-ontolens-asset="{name}"]')
            assert script and not script.get('src')
            license_text = (static / f'{library}-LICENSE.txt').read_text(encoding='utf-8')
            assert license_text in script.string


def test_embedded_cytoscape_and_fcose_execute_without_network_or_asset_files(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required to execute embedded graph libraries')
    source = tmp_path / 'offline.ttl'
    source.write_text(ONTOLOGY, encoding='utf-8')
    page = generate(source, tmp_path / 'offline.html')
    soup = BeautifulSoup(page.read_text(encoding='utf-8'), 'html.parser')
    embedded = [tag.string for tag in soup.select('script[data-ontolens-asset]')]
    script = '''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const noNetwork = () => {throw new Error('External resources are not available');};
const context = vm.createContext({console, setTimeout, clearTimeout, assert,
  fetch:noNetwork, XMLHttpRequest:noNetwork, WebSocket:noNetwork});
''' + f'for (const code of {json.dumps(embedded)}) vm.runInContext(code, context);\n' + '''
vm.runInContext(`
const cy = cytoscape({headless:true, styleEnabled:true, layout:{name:'preset'},
  elements:[{data:{id:'a'}},{data:{id:'b'}},{data:{id:'edge',source:'a',target:'b'}}]});
cy.layout({name:'fcose',animate:false,randomize:true,quality:'proof',packComponents:false}).run();
assert.equal(cy.nodes().length,2);
assert(cy.nodes().every(n=>Number.isFinite(n.position('x')) && Number.isFinite(n.position('y'))));
assert.equal(typeof OntolensGraphLabels.placeLabels,'function');
assert.equal(typeof OntolensGraphLayout,'object');
cy.destroy();
`, context);
'''
    result = subprocess.run([node], input=script, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr[-3000:]


def test_inline_assets_preserve_script_and_style_boundaries(tmp_path):
    script = tmp_path / 'closing.js'
    script.write_text('const text = "</ScRiPt><p>not markup</p>";\n//# sourceMappingURL=closing.js.map', encoding='utf-8')
    style = tmp_path / 'closing.css'
    style.write_text('/* </STYLE><p>not markup</p> */', encoding='utf-8')
    html = f'<script>{inline_script(str(script))}</script><style>{inline_style(str(style))}</style>'
    soup = BeautifulSoup(html, 'html.parser')
    assert len(soup.select('script')) == 1
    assert len(soup.select('style')) == 1
    assert not soup.select('p')
    assert '<\\/ScRiPt>' in soup.script.string
    assert 'sourceMappingURL' not in soup.script.string
