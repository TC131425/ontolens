import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest


def test_disconnected_graph_uses_compact_non_overlapping_layout():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required to execute Cytoscape layouts')
    root = Path(__file__).parents[1] / 'src/ontolens'
    template = (root / 'templates/documentation.html.j2').read_text(encoding='utf-8')
    functions = '\n'.join(re.search(
        r'function ' + name + r'\([^\n]*\) \{.*?\n      \}', template, re.S
    )[0] for name in ('stopLayout', 'runLayout'))
    script = '''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({console, setTimeout, clearTimeout, assert});
'''
    for name in ('cytoscape.min', 'layout-base', 'cose-base', 'cytoscape-fcose', 'graph-layout', 'pdf_graph'):
        script += f'vm.runInContext(fs.readFileSync({json.dumps(str(root / "static" / (name + ".js")))}, "utf8"), context);\n'
    exercise = '''
let focusId = null, layoutRevision = 0, activeLayout = null, edgeLabelFrame = null;
const cancelAnimationFrame = () => {}, positionEdgeLabels = () => {}, fitGraph = () => {};
const layoutOptions = {name:'breadthfirst', directed:true};
const nodes = Array.from({length:16}, (_,i) => ({data:{id:'n'+i}}));
const edges = [[0,3],[1,3],[2,3],[0,4],[1,4],[10,13],[10,14],[10,15]]
  .map(([s,t],i) => ({data:{id:'e'+i,source:'n'+s,target:'n'+t}}));
const cy = cytoscape({headless:true, styleEnabled:true, elements:{nodes,edges},
  style:[{selector:'node',style:{width:240,height:70}}], layout:{name:'preset'}});
''' + functions + '''
function verify() {
  const boxes = cy.nodes().map(n => n.boundingBox());
  for (let i=0;i<boxes.length;i++) {
    const a=boxes[i];
    assert(Number.isFinite(a.x1) && Number.isFinite(a.y1));
    for (const b of boxes.slice(i+1))
      assert(a.x2<=b.x1 || b.x2<=a.x1 || a.y2<=b.y1 || b.y2<=a.y1,
        'Class rectangles must not overlap');
  }
  const bounds = cy.elements().boundingBox();
  assert(bounds.w / bounds.h < 2.5, 'Avoid a single wide row of disconnected classes');
  assert(cy.nodes().every(n => n.hasClass('component-overview')));
}
for (let i=0;i<4;i++) {runLayout(); verify();}
assert.equal(pdfGraphLayout(cy).name, 'fcose');
assert.equal(pdfGraphLayout(cy).tile, true);
cy.layout({...pdfGraphLayout(cy),animate:false}).run();
OntolensGraphLayout.separateNodes(cy);
verify();
const ontologies = [{uri:'https://example.org/external#',label:'ext'}];
assert.equal(pdfGraphLabel({label:'https://example.org/external#DictionaryReferenceDocument',
  ontology:ontologies[0].uri,kind:'external-class'},ontologies), 'ext:\\nDictionary Reference Document');
assert.equal(pdfGraphLabel({label:'isoprops:DictionarySubset',kind:'external-class'},[]), 'isoprops:\\nDictionary Subset');
assert.equal(pdfGraphLabel({label:'xsd:string',kind:'literal'},[]), 'xsd:string');
assert.equal(cy.nodes().length,16);
assert.equal(cy.edges().length,8);
cy.edges().remove();
runLayout();
verify();
cy.elements().remove();
runLayout();
cy.add({data:{id:'alone'}});
runLayout();
assert(!cy.nodes().hasClass('component-overview'));
assert.equal(pdfGraphLayout(cy).name, 'grid');
assert(Number.isFinite(cy.nodes()[0].position('x')));
cy.elements().remove();
cy.add([{data:{id:'a'},position:{x:0,y:0}},
  {data:{id:'b'},position:{x:20,y:10}},
  {data:{id:'c'},position:{x:40,y:20}},
  {data:{id:'far'},position:{x:2000,y:0}}]);
OntolensGraphLayout.separateNodes(cy);
const separated = cy.nodes().map(n=>n.boundingBox());
for(let i=0;i<separated.length;i++) {
  const a=separated[i];
  for(const b of separated.slice(i+1))
    assert(a.x2+23<=b.x1 || b.x2+23<=a.x1 || a.y2+23<=b.y1 || b.y2+23<=a.y1);
}
assert.equal(cy.getElementById('far').position('x'),2000);
const positions=cy.nodes().map(n=>({...n.position()}));
OntolensGraphLayout.separateNodes(cy);
assert.deepEqual(cy.nodes().map(n=>({...n.position()})),positions);
cy.destroy();
'''
    script += f'vm.runInContext({json.dumps(exercise)}, context);'
    result = subprocess.run([node], input=script, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr[-3000:]
