import json
import re
import shutil
import subprocess

import pytest
from bs4 import BeautifulSoup

from ontolens.render import generate
from test_content import ONTOLOGY


def test_neighborhood_layout_and_fit(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required to execute graph layout configuration')
    source = tmp_path / 'layout.ttl'
    source.write_text(ONTOLOGY, encoding='utf-8')
    output = generate(source, tmp_path / 'layout.html')
    html = output.read_text(encoding='utf-8')
    soup = BeautifulSoup(html, 'html.parser')
    assert not soup.select('script[src]')
    assert not (output.parent / 'assets').exists()
    for name in ['layout-base', 'cose-base', 'cytoscape-fcose']:
        assert soup.select_one(f'script[data-ontolens-asset="{name}.js"]')
    layout = soup.select_one('script[data-ontolens-asset="graph-layout.js"]').string
    names = ['neighborhoodLabel', 'overviewLabel', 'neighborhoodEdgeLabel', 'graphTextLines', 'stopLayout', 'fitGraph', 'changeGraphZoom', 'runLayout']
    functions = '\n'.join(
        re.search(r'function ' + name + r'\([^\n]*\) \{.*?\n      \}', html, re.S)[0]
        for name in names
    )
    script = f'const OntolensGraphLayout = new Function("module", {json.dumps(layout + ";return module.exports;")})({{exports:{{}}}});\n' + '''
const assert = require('node:assert/strict');
const window = {ontolensVisualization:{ontologies:[{uri:'https://w3id.org/tempo#',label:'https://w3id.org/tempo#'}]}};
const node = data => ({data:key=>key ? data[key] : data});
const labelContext = {measureText:text=>({width:text.length * 8})};
function positionEdgeLabels() {}
function cancelAnimationFrame() {}
''' + functions + '''
assert.equal(neighborhoodLabel(node({label:'https://w3id.org/tempo#Unit',ontology:'https://w3id.org/tempo#'})), 'tempo:\\nUnit');
assert.equal(neighborhoodLabel(node({label:'Alphanumerical information'})), 'Alphanumerical information');
assert.equal(neighborhoodLabel(node({label:'Other',ontology:'https://w3id.org/tempo#'})), 'Other');
assert.equal(overviewLabel(node({label:'isoprops:DictionaryReferenceDocument',kind:'external-class'})), 'isoprops:\\nDictionary Reference Document');
assert.equal(overviewLabel(node({label:'https://w3id.org/tempo#TimeInterval',kind:'external-class',ontology:'https://w3id.org/tempo#'})), 'tempo:\\nTime Interval');
assert.equal(overviewLabel(node({label:'xsd:string',kind:'literal'})), 'xsd:string');
assert.equal(neighborhoodEdgeLabel(node({label:'has unit',href:'#hasUnit'})), 'has unit');
assert.equal(neighborhoodEdgeLabel(node({label:'A'.repeat(70),href:'#hasUnit'})), 'hasUnit');
assert.equal(neighborhoodEdgeLabel(node({label:'',href:'#Class'})), '');
assert.deepEqual(graphTextLines('Alphanumerical information', 180, 15), ['Alphanumerical','information']);
assert.deepEqual(graphTextLines('tempo:\\nUnit', 180, 15), ['tempo:','Unit']);
let focusId = 'class';
let activeLayout = null;
let layoutRevision = 0;
let edgeLabelFrame = null;
let count = 12;
let zoom = 4;
let fitted = 0;
let centered = 0;
let options;
let oldStop;
let components = 1;
let compact = false;
const elements = {components:()=>({length:components}), toggleClass:(name,value)=>{compact=value;},hasClass:()=>compact};
const layoutOptions = {name:'breadthfirst',directed:true};
const cy = {
  nodes:()=>({length:count,map:()=>[]}), elements:()=>elements,
  width:()=>800, height:()=>600, resize:()=>{}, stop:()=>{},
  fit:(target,padding)=>{assert.equal(target,elements);fitted++;assert.equal(padding,focusId?24:34);},
  zoom:value=>{if(value !== undefined) zoom=typeof value==='object'?value.level:value;return zoom;},
  minZoom:()=>.15, maxZoom:()=>2.6,
  center:()=>centered++,
  layout:config=>{options=config;return {run:()=>{},stop:()=>config.stop()};}
};
runLayout();
assert.equal(options.name,'fcose');
assert.equal(options.fit,false);
assert.equal(options.nodeDimensionsIncludeLabels,true);
assert.equal(options.quality,'proof');
assert.equal(options.boundingBox,undefined); // Never squeeze laid-out rectangles into overlapping positions.
assert.equal(fitted,0); // Fit after positions have settled, not against the old graph.
options.stop();
assert.equal(fitted,1);
assert.equal(zoom,1.8);
assert.equal(centered,1);
oldStop=options.stop;
runLayout();
oldStop();
assert.equal(fitted,1); // Stale layout callbacks cannot zoom a newer view.
options.stop();
assert.equal(fitted,2);
count=2;
runLayout(false);
assert.equal(options.animate,false);
assert.equal(options.name,'fcose');
options.stop();
count=1;
runLayout(false);
assert.equal(options.name,'grid');
options.stop();
count=0;
const before=fitted;
fitGraph();
assert.equal(fitted,before);
count=12;
focusId=null;
zoom=1;
runLayout(false);
assert.equal(options.name,'breadthfirst');
assert.equal(options.directed,true);
options.stop();
assert.equal(zoom,1.1);
components=9;
runLayout();
assert.equal(options.name,'fcose');
assert.equal(options.tile,true);
assert.equal(options.packComponents,false);
assert.equal(options.tilingPaddingHorizontal,28);
assert.equal(options.tilingPaddingVertical,28);
assert.equal(compact,true);
options.stop();
components=1;
runLayout();
assert.equal(options.name,'breadthfirst');
assert.equal(compact,false);
options.stop();
zoom=.2;
fitGraph(false);
assert.equal(zoom,.2); // Explicit overview may zoom out below readable size.
fitGraph();
assert.equal(zoom,1.1);
zoom=2.5;
changeGraphZoom(1.25);
assert.equal(zoom,2.6);
zoom=.16;
changeGraphZoom(.8);
assert.equal(zoom,.15);
'''
    subprocess.run([node], input=script, text=True, check=True, capture_output=True, timeout=15)
