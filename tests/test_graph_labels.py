import json
import shutil
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from ontolens.render import generate
from test_content import ONTOLOGY


def test_label_placement_avoids_nodes_and_other_labels(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required to execute label placement')
    source = tmp_path / 'labels.ttl'
    source.write_text(ONTOLOGY, encoding='utf-8')
    output = generate(source, tmp_path / 'labels.html')
    soup = BeautifulSoup(output.read_text(encoding='utf-8'), 'html.parser')
    helper = soup.select_one('script[data-ontolens-asset="graph-labels.js"]').string
    assert not soup.select('script[src]')
    assert not (output.parent / 'assets').exists()
    arrows = soup.select('#graph-document-icon path')
    assert [path['d'] for path in arrows] == ['M7 7h10v10', 'M7 17 17 7']
    scripts = [tag.string for tag in soup.select('script:not([src])')
               if tag.get('type') != 'application/ld+json']
    script = (
        "const assert = require('node:assert/strict');\n"
        "const vm = require('node:vm');\n"
        f'const api = new Function("module", {json.dumps(helper + ";return module.exports;")})({{exports:{{}}}});\n'
        f"for (const code of {json.dumps(scripts)}) new vm.Script(code);\n"
    ) + '''
const obstacle = (x,y,w,h) => ({x1:x-w/2,y1:y-h/2,x2:x+w/2,y2:y+h/2});
const label = (id,source,target,width=120,height=34) => ({id,source,target,width,height,
  origin:{x:(source.x+target.x)/2,y:(source.y+target.y)/2}});
function verify(labels, obstacles) {
  const placed=api.placeLabels(labels,obstacles);
  assert.equal(placed.size,labels.length);
  const occupied=obstacles.slice();
  for(const point of placed.values()) {
    assert(Number.isFinite(point.x) && Number.isFinite(point.y));
    assert.equal(point.crowded,occupied.some(box=>api.overlaps(point.box,box,8)));
    occupied.push(point.box);
  }
  assert.deepEqual(placed,api.placeLabels([...labels].reverse(),obstacles));
  return placed;
}
const source={x:0,y:0}, target={x:600,y:0};
const nodes=[obstacle(0,0,210,65),obstacle(600,0,210,65),obstacle(300,0,200,70)];
const parallel=Array.from({length:12},(_,i)=>label('p'+i,source,target,100+i*4,34+i%3*15));
verify(parallel,nodes);
verify([label('loop',source,source)], [obstacle(0,0,220,80)]);
assert.equal(verify([],nodes).size,0);
const fallback=verify([label('crowded',source,target)],[obstacle(0,0,10000,10000)]);
assert(fallback.get('crowded').crowded);
assert(Math.abs(fallback.get('crowded').y) <= 96);
const dense = Array.from({length:60},(_,i)=>label('dense'+i,source,target,180,46));
const densePositions = verify(dense,nodes);
assert([...densePositions.values()].every(point=>point.x>=132 && point.x<=468 && Math.abs(point.y)<=96));
assert([...densePositions.values()].some(point=>point.crowded));
const distantNode = obstacle(100,-20000,200,60);
assert.deepEqual(api.placeLabels(dense,nodes),api.placeLabels(dense,[...nodes,distantNode]));
for (let count=3;count<=30;count+=3) {
  const neighbors=Array.from({length:count},(_,i)=>({x:Math.cos(i/count*2*Math.PI)*400,y:Math.sin(i/count*2*Math.PI)*300}));
  verify(neighbors.map((point,i)=>label('star'+i,source,point)),
    [obstacle(0,0,220,75),...neighbors.map(point=>obstacle(point.x,point.y,200,60))]);
}
const initial=verify([label('move',source,target)],[]).get('move');
const moved=verify([label('move',source,target)],[initial.box]).get('move');
assert.notDeepEqual({x:initial.x,y:initial.y},{x:moved.x,y:moved.y});
for(const end of [{x:600,y:0},{x:0,y:600},{x:300,y:400}]) {
  const point={x:220,y:-150};
  const bend=api.bendThrough(source,end,point);
  const length=Math.hypot(end.x,end.y);
  const x=end.x*bend.weight-end.y/length*bend.distance;
  const y=end.y*bend.weight+end.x/length*bend.distance;
  assert(Math.abs(x-point.x)<1e-8 && Math.abs(y-point.y)<1e-8);
}
assert.equal(api.bendThrough(source,source,{x:10,y:10}),null);
const block=obstacle(300,0,120,80);
assert(api.segmentCrossesBox(source,target,block));
assert(!api.segmentCrossesBox({x:0,y:100},{x:600,y:100},block));
assert(api.segmentCrossesBox({x:300,y:-100},{x:300,y:100},block));
const routed=verify([label('detour',source,target)],[block]).get('detour');
assert(!api.segmentCrossesBox(source,routed,block));
assert(!api.segmentCrossesBox(routed,target,block));
'''
    subprocess.run([node], input=script, text=True, capture_output=True, check=True, timeout=20)


def test_svg_keeps_label_anchors_bends_and_foreground_layer():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required to execute SVG export')
    template = (Path(__file__).parents[1] / 'src/ontolens/templates/documentation.html.j2').read_text(encoding='utf-8')
    export = template[template.index('      function exportSvg() {'):]
    export = export[:export.index('\n      document.getElementById("reset-graph-layout")')]
    script = '''
const assert = require('node:assert/strict');
const focusId = 'focus';
const edgeLabelPositions = new Map([['one',{x:100,y:80,box:{x1:55,y1:65,x2:145,y2:95}}],
  ['two',{x:100,y:130,box:{x1:55,y1:115,x2:145,y2:145}}]]);
const makeEdge = id => ({
  id:()=>id, source:()=>({position:()=>({x:0,y:0})}), target:()=>({position:()=>({x:200,y:0})}),
  data:key=>({edgeKind:'object-property',label:'Label '+id,arrow:'triangle'}[key]),
  style:key=>({'font-size':'14','font-weight':'400','curve-style':'segments',label:'Label '+id}[key]),
  segmentPoints:()=>[{x:100,y:80}], sourceEndpoint:()=>({x:20,y:10}), targetEndpoint:()=>({x:180,y:10})
});
const cy = {elements:()=>({boundingBox:()=>({x1:0,y1:0,w:200,h:150})}),
  edges:selector=>selector?[]:[makeEdge('one'),makeEdge('two')], nodes:()=>[]};
const positionEdgeLabels=()=>{}, datatypeLegendGroups=()=>[], ontologyLegendEntries=()=>[];
const neighborhoodEdgeLabel=edge=>edge.data('label'), graphTextLines=text=>[text];
const xmlEscape=text=>text, safeFileName=()=> 'graph.svg';
let result;
const downloadBlob=blob=>{result=blob;};
''' + export + '''
exportSvg();
result.text().then(svg=>{
  assert(svg.includes('d="M20 10 L100 80 L180 10"'));
  assert(svg.includes('<text x="100" y="84.9"'));
  assert(svg.includes('<text x="100" y="134.9"'));
  assert(svg.lastIndexOf('<path d="M20') < svg.indexOf('<text x="100"'));
  assert(svg.includes('width="90" height="30" fill="#fbfcfd"'));
});
'''
    subprocess.run([node], input=script, text=True, capture_output=True, check=True, timeout=20)
