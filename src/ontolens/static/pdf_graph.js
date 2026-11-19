// Only trusted code runs during PDF rendering; document scripts are removed.
function pdfGraphLabel(data, ontologies) {
  return OntolensGraphLayout.compactLabel(data, ontologies).replace(/\S{24,}/g,
    word => word.match(/.{1,18}/g).join('\n'));
}

function pdfGraphLayout(cy) {
  if (cy.elements().components().length > 1) {
    return OntolensGraphLayout.networkOptions(cy.nodes().length, true);
  }
  const cols = Math.max(1, Math.ceil(Math.sqrt(cy.nodes().length)));
  return {name:'grid', cols,
    boundingBox:{x1:0,y1:0,w:cols*280,h:Math.ceil(cy.nodes().length/cols)*180},
    avoidOverlap:true, nodeDimensionsIncludeLabels:true, padding:10,
    sort:(a,b) => b.degree() - a.degree() || a.id().localeCompare(b.id())};
}

function positionPdfGraphLabels(cy, context) {
  const labels = [];
  const obstacles = cy.nodes().map(node => node.boundingBox({includeLabels:true, includeOverlays:false}));
  cy.edges().forEach(edge => {
    const text = String(edge.style('label') || '');
    if (!text) return;
    const font = parseFloat(edge.style('font-size'));
    context.font = `${font}px Arial`;
    const lines = [];
    text.split('\n').forEach(paragraph => {
      let line = '';
      paragraph.split(/\s+/).forEach(word => {
        const next = line ? `${line} ${word}` : word;
        if (line && context.measureText(next).width > 180) {lines.push(line); line = word;}
        else line = next;
      });
      lines.push(line);
    });
    labels.push({id:edge.id(), origin:edge.midpoint(), source:edge.source().position(),
      target:edge.target().position(), width:Math.max(...lines.map(line=>context.measureText(line).width))+12,
      height:lines.length*font*1.2+12});
  });
  OntolensGraphLabels.placeLabels(labels, obstacles).forEach((point,id) => {
    const edge = cy.getElementById(id);
    const bend = OntolensGraphLabels.bendThrough(edge.source().position(),edge.target().position(),point);
    if (bend && edge.source().id() !== edge.target().id() && !String(edge.data('edgeKind')).startsWith('equivalent')) {
      edge.style({'curve-style':'segments','edge-distances':'node-position',
        'segment-weights':bend.weight,'segment-distances':bend.distance});
    }
    const midpoint = edge.midpoint();
    edge.style({'text-margin-x':point.x-midpoint.x,'text-margin-y':point.y-midpoint.y});
  });
}

async function renderPdfGraph(elements) {
  await document.fonts.ready;
  const ontologies = elements.ontologies || [];
  const container = document.createElement('div');
  container.style.cssText = 'width:1200px;height:800px;position:absolute;left:0;top:0;background:white';
  document.body.append(container);
  const cy = cytoscape({container, elements:{nodes:elements.nodes,edges:elements.edges}, style: [
    {selector:'node', style:{label:node => pdfGraphLabel(node.data(), ontologies),
      'font-size':22, 'font-family':'Arial', 'font-weight':600, 'text-wrap':'wrap', 'text-max-width':180,
      'text-valign':'center', 'text-halign':'center', color:'#fff', 'background-color':n=>n.data('color') || '#155c63',
      'border-width':2, 'border-color':n=>n.data('border') || '#0f4449', shape:'round-rectangle', width:180, height:'label', padding:'12px'}},
    {selector:'node[kind = "literal"]', style:{'background-color':'#fff', color:'#0f4449', shape:'rectangle'}},
    {selector:'node[kind = "missing-endpoint"]', style:{label:'', width:48, height:48}},
    {selector:'edge', style:{label:'data(label)', width:1.5, 'curve-style':'bezier', 'target-arrow-shape':'triangle',
      'line-color':'#1b3437', 'target-arrow-color':'#1b3437', 'font-size':18, 'font-family':'Arial',
      'text-rotation':'none','text-wrap':'wrap','text-max-width':180,'line-height':1.2,
      'text-margin-y':-8, 'text-background-color':'#fff', 'text-background-opacity':1, 'text-background-padding':3}},
    {selector:'edge[edgeKind = "subClassOf"]', style:{label:'', 'line-style':'solid'}},
    {selector:'edge[edgeKind = "object-property"]', style:{'line-style':'dashed'}},
    {selector:'edge[edgeKind = "datatype-property"]', style:{'line-style':'dotted', 'text-rotation':'none'}},
    {selector:'edge[edgeKind = "equivalent-class"], edge[edgeKind = "equivalent-class-parallel"]',
      style:{'curve-style':'segments', 'segment-distances':'data(offset)', 'segment-weights':0.5,
        'target-arrow-shape':'none', 'text-rotation':'none'}}
  ], layout:{name:'preset'}, pixelRatio:2});
  await new Promise(resolve => cy.layout({...pdfGraphLayout(cy),fit:false,animate:false,stop:resolve}).run());
  if (cy.elements().components().length > 1) OntolensGraphLayout.distributeNodes(cy, 1200, 800);
  else OntolensGraphLayout.separateNodes(cy);
  positionPdfGraphLabels(cy, document.createElement('canvas').getContext('2d'));
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const png = cy.png({full:true, maxWidth:3000, maxHeight:2200, bg:'#fff'});
  cy.destroy(); container.remove();
  const image = document.createElement('img');
  image.src = png; image.className = 'pdf-graph'; image.alt = 'Ontology graph';
  document.getElementById('ontology-graph').replaceWith(image);
  await image.decode();
}
