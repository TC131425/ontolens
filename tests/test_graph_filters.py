import json
import re
import shutil
import subprocess

import pytest

from ontolens.render import generate
from test_content import ONTOLOGY


def test_graph_filters_share_checked_means_visible(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required to execute graph filters')
    source = tmp_path / 'filters.ttl'
    source.write_text(ONTOLOGY + '''
ex:external a owl:ObjectProperty ; rdfs:domain ex:Thing ; rdfs:range <https://external.example/Class> .
ex:data a owl:DatatypeProperty ; rdfs:domain ex:Thing ; rdfs:range rdfs:Literal .
ex:externalData a owl:DatatypeProperty ; rdfs:domain <https://external.example/Class> ; rdfs:range <http://www.w3.org/2001/XMLSchema#string> .
<https://external.example/Isolated> a owl:Class .
''', encoding='utf-8')
    html = generate(source, tmp_path / 'filters.html', include_external_classes=True).read_text(encoding='utf-8')
    elements = json.loads(re.search(r'window\.ontolensVisualization = (.*);', html)[1])['elements']
    function = re.search(r'function visibleElements\(\) \{.*?\n      \}', html, re.S)[0]
    neighborhood = re.search(r'function neighborhoodElements\(elements, id\) \{.*?\n      \}', html, re.S)[0]
    script = 'const originalElements = ' + json.dumps(elements) + ';\n' + neighborhood + '\n' + function + '''
const assert = require('node:assert/strict');
let focusId = null;
const datatypeToggle = {checked:true};
const externalToggle = {checked:true};
assert.deepEqual(visibleElements(), originalElements);
for (const external of [false, true]) {
  for (const datatype of [false, true]) {
    externalToggle.checked = external;
    datatypeToggle.checked = datatype;
    const visible = visibleElements();
    assert.equal(visible.nodes.some(n => n.data.kind === 'external-class'), external);
    assert.equal(visible.nodes.some(n => n.data.id === 'https://external.example/Isolated'), external);
    assert.equal(visible.nodes.some(n => n.data.kind === 'literal'), datatype);
    assert.equal(visible.nodes.some(n => n.data.id === 'http://www.w3.org/2001/XMLSchema#string'), external && datatype);
    assert.equal(visible.edges.some(e => e.data.properties?.some(p => p.href === '#externalData')), external && datatype);
    const ids = new Set(visible.nodes.map(n => n.data.id));
    assert(visible.edges.every(e => ids.has(e.data.source) && ids.has(e.data.target)));
  }
}
assert.deepEqual(visibleElements(), originalElements);
focusId = 'https://external.example/Class';
const focused = visibleElements();
assert.equal(focused.nodes.length, 3);
assert(focused.nodes.some(n => n.data.kind === 'literal'));
externalToggle.checked = false;
assert(!visibleElements().nodes.some(n => n.data.kind === 'external-class'));
focusId = null;
externalToggle.checked = true;
assert.deepEqual(visibleElements(), originalElements);
// A property-only ontology must not leave detached literal nodes behind.
const savedNodes = originalElements.nodes;
const savedEdges = originalElements.edges;
originalElements.nodes = savedNodes.filter(n => n.data.kind !== 'class');
originalElements.edges = savedEdges.filter(e => e.data.properties?.some(p => p.href === '#externalData'));
externalToggle.checked = false;
assert.deepEqual(visibleElements(), {nodes:[], edges:[]});
externalToggle.checked = true;
assert.equal(visibleElements().nodes.length, 3);
assert.equal(visibleElements().edges.length, 1);
originalElements.nodes = savedNodes;
originalElements.edges = savedEdges;
focusId = 'https://external.example/Isolated';
assert.equal(visibleElements().nodes.length, 1);
assert.equal(visibleElements().edges.length, 0);
focusId = null;
const testGraph = {
  nodes: ['a', 'b', 'c', 'd', 'alone'].map(id => ({data:{id}})),
  edges: [['a','b'], ['c','a'], ['b','d'], ['c','b']].map(([source,target]) => ({data:{source,target}}))
};
assert.deepEqual(neighborhoodElements(testGraph, 'a').nodes.map(n => n.data.id), ['a','b','c']);
assert.equal(neighborhoodElements(testGraph, 'a').edges.length, 3);
assert.deepEqual(neighborhoodElements(testGraph, 'alone'), {nodes:[{data:{id:'alone'}}], edges:[]});
assert.deepEqual(neighborhoodElements(testGraph, null), testGraph);
'''
    subprocess.run([node], input=script, text=True, check=True, capture_output=True, timeout=15)
