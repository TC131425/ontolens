import json
from pathlib import Path
import shutil
import subprocess

import pytest


def test_dense_center_is_spread_to_viewport_without_losing_nodes():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required to execute graph distribution')
    static = Path(__file__).parents[1] / 'src/ontolens/static'
    script = (
        "const assert = require('node:assert/strict');\n"
        f"const cytoscape = require({json.dumps(str(static / 'cytoscape.min.js'))});\n"
        f"const layout = require({json.dumps(str(static / 'graph-layout.js'))});\n"
    ) + '''
const nodes=Array.from({length:48},(_,i)=>({data:{id:'n'+i},position:i<36
  ? {x:(i%6)*12,y:Math.floor(i/6)*12}
  : {x:Math.cos(i)*2000,y:Math.sin(i)*1200}}));
for(const [width,height] of [[1500,900],[900,1500],[390,520]]) {
  const cy=cytoscape({headless:true,styleEnabled:true,elements:nodes,
    style:[{selector:'node',style:{width:160,height:60}}],layout:{name:'preset'}});
  layout.distributeNodes(cy,width,height);
  const bounds=cy.nodes().boundingBox({includeLabels:true,includeOverlays:false});
  assert(Math.abs(bounds.w/bounds.h-width/height)<.18,'Respect the viewport aspect ratio');
  const boxes=cy.nodes().map(n=>n.boundingBox());
  for(let i=0;i<boxes.length;i++) for(const b of boxes.slice(i+1)) {
    const a=boxes[i];
    assert(a.x2+23<=b.x1 || b.x2+23<=a.x1 || a.y2+23<=b.y1 || b.y2+23<=a.y1);
  }
  const center={x:(bounds.x1+bounds.x2)/2,y:(bounds.y1+bounds.y2)/2};
  const central=cy.nodes().filter(n=>Math.abs(n.position('x')-center.x)<bounds.w/4 &&
    Math.abs(n.position('y')-center.y)<bounds.h/4);
  assert(central.length<24,'Do not keep most classes in the central quarter');
  assert.equal(cy.nodes().length,48);
  assert(cy.nodes().every(n=>Number.isFinite(n.position('x')) && Number.isFinite(n.position('y'))));
  cy.destroy();
}
const tiny=cytoscape({headless:true,styleEnabled:true,elements:nodes.slice(0,2),
  style:[{selector:'node',style:{width:160,height:60}}],layout:{name:'preset'}});
layout.distributeNodes(tiny,800,600);
const [a,b]=tiny.nodes().map(n=>n.boundingBox());
assert(a.x2<b.x1 || b.x2<a.x1 || a.y2<b.y1 || b.y2<a.y1);
tiny.destroy();
'''
    result = subprocess.run([node], input=script, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr[-2500:]
