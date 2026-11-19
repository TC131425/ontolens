/* Local, read-only A-Box explorer. RDF text is always rendered as text nodes. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('abox-data').textContent);
  const config = JSON.parse(document.getElementById('abox-config').textContent);
  const el = id => document.getElementById(id);
  const resources = new Map(data.instances.map(n => [n.resource.id, n]));
  const ids = new Map(data.instances.map((n, i) => [n.resource.id, 'n' + i]));
  const adjacency = new Map(data.instances.map(n => [n.resource.id, new Set()]));
  data.relations.forEach(r => {adjacency.get(r.source).add(r.target); adjacency.get(r.target).add(r.source);});
  let selected = null;
  let focusId = null;
  let cy = null;
  let matches = [];
  const typeNames = new Map();
  const typeCounts = new Map();
  data.instances.forEach(n => n.types.forEach(t => {typeNames.set(t.id, t.curie); typeCounts.set(t.id, (typeCounts.get(t.id) || 0) + 1);}));
  const sortedTypes = [...typeNames].sort((a,b) => a[1].localeCompare(b[1]));
  const namespace = id => id.slice(0, Math.max(id.lastIndexOf('#'), id.lastIndexOf('/'), id.lastIndexOf(':')) + 1);
  const palette = ['#155c63', '#397969', '#546f92', '#946744', '#776281', '#646f53'];
  const namespaces = [...new Set(sortedTypes.map(([id]) => namespace(id)))].sort();
  const colors = new Map(namespaces.map((ns, index) => [ns, palette[index] || `hsl(${Math.round(index * 137.508) % 360}, 32%, 38%)`]));
  const legendMedia = matchMedia('(max-width: 620px)');
  el('graph-legend').open = !legendMedia.matches;
  legendMedia.addEventListener('change', event => {el('graph-legend').open = !event.matches;});
  let hoveredNamespace = null;
  let focusedNamespace = null;
  function highlightNamespace() {
    if(!cy) return;
    const ns = hoveredNamespace || focusedNamespace;
    cy.batch(() => {
      cy.elements().removeClass('legend-dim');
      if(!ns || !el('graph-legend').open) return;
      const matching = cy.nodes().filter(node => {
        const instance = resources.get(node.data('resource'));
        return instance?.types.some(type => namespace(type.id) === ns);
      });
      if(!matching.length) return;
      const edges = matching.connectedEdges();
      cy.elements().difference(matching.union(edges)).addClass('legend-dim');
    });
  }
  function updateLegend() {
    const container = el('namespace-legend');
    container.replaceChildren(); hoveredNamespace = null; focusedNamespace = null;
    namespaces.forEach(ns => {
      const type = sortedTypes.find(([id]) => namespace(id) === ns);
      const curie = type[1];
      const label = !curie.startsWith('<') && !curie.includes('://') && curie.includes(':') ? curie.slice(0, curie.indexOf(':') + 1) : ns;
      const entry = element('span', undefined, 'namespace-entry');
      entry.tabIndex = 0; entry.title = ns; entry.dataset.namespace = ns;
      const visible = cy.nodes().some(node => resources.get(node.data('resource'))?.types.some(t => namespace(t.id) === ns));
      entry.setAttribute('aria-disabled', String(!visible));
      entry.setAttribute('aria-label', `${label} ${ns}`);
      const swatch = element('span', undefined, 'namespace-swatch');
      swatch.style.setProperty('--namespace-color', colors.get(ns)); swatch.setAttribute('aria-hidden', 'true');
      entry.append(swatch, document.createTextNode(label));
      entry.onmouseenter = () => {hoveredNamespace = ns; highlightNamespace();};
      entry.onmouseleave = () => {hoveredNamespace = null; highlightNamespace();};
      entry.onfocus = () => {focusedNamespace = ns; highlightNamespace();};
      entry.onblur = () => {focusedNamespace = null; highlightNamespace();};
      container.append(entry);
    });
    if(!namespaces.length) container.append(element('span', 'Keine typisierten Instanzen', 'record-muted'));
  }
  el('graph-legend').addEventListener('toggle', () => {
    if(!el('graph-legend').open) {hoveredNamespace = null; focusedNamespace = null;}
    highlightNamespace();
  });
  sortedTypes.forEach(([id, name]) => {const o = document.createElement('option'); o.value = id; o.textContent = `${name} (${typeCounts.get(id)})`; el('class-filter').append(o);});
  const untyped = document.createElement('option'); untyped.value = '__untyped'; untyped.textContent = 'Ohne angegebenen Typ'; el('class-filter').append(untyped);
  function element(tag, text, className) {const n = document.createElement(tag); if(text !== undefined) n.textContent = text; if(className) n.className = className; return n;}
  function short(text, limit) {return text.length > limit ? text.slice(0, limit - 1) + '\u2026' : text;}
  const nodeFaces = new Map();
  function nodeFace(instance) {
    if(nodeFaces.has(instance.resource.id)) return nodeFaces.get(instance.resource.id);
    const color = colors.get(namespace(instance.types[0]?.id || instance.resource.id)) || '#155c63';
    const rows = [instance.resource.label, ...instance.types.map(t => t.curie)];
    if(rows.length === 1) rows.push(instance.external ? 'Externe Referenz' : 'Ohne Typ');
    const canvas = document.createElement('canvas'), ctx = canvas.getContext('2d');
    ctx.font = '14px Arial';
    const width = Math.min(320, Math.max(200, ...rows.map(text => ctx.measureText(text).width + 28)));
    const rowHeight = 28, height = rows.length * rowHeight;
    // Raster backgrounds keep both compartments inside the exported Cytoscape image.
    canvas.width = Math.ceil(width * 3); canvas.height = height * 3;
    ctx.scale(3, 3); ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, width, height);
    ctx.font = '14px Arial'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    rows.forEach((text, index) => {
      let fitted = text;
      while(ctx.measureText(fitted).width > width - 24 && fitted.length > 1) {
        fitted = fitted.replace(/\u2026$/, '').slice(0, -1) + '\u2026';
      }
      if(index) {
        ctx.fillStyle = colors.get(namespace(instance.types[index - 1]?.id || instance.resource.id)) || color;
        ctx.fillRect(0, index * rowHeight, width, rowHeight);
        ctx.strokeStyle = color; ctx.globalAlpha = .25; ctx.lineWidth = .7;
        ctx.beginPath(); ctx.moveTo(0, index * rowHeight); ctx.lineTo(width, index * rowHeight); ctx.stroke(); ctx.globalAlpha = 1;
      }
      ctx.fillStyle = index ? '#ffffff' : '#202124'; ctx.fillText(fitted, width / 2, (index + .5) * rowHeight);
    });
    const face = {face:canvas.toDataURL('image/png'), width, height, color};
    nodeFaces.set(instance.resource.id, face); return face;
  }
  function safeLink(url, text) {const n = element('a', text); if(/^https?:\/\//i.test(url)) {n.href = url; n.target = '_blank'; n.rel = 'noopener noreferrer';} return n;}
  function list() {
    const query = el('search').value.toLocaleLowerCase().trim(), type = el('class-filter').value;
    matches = data.instances.filter(n => (!type || (type === '__untyped' ? !n.types.length : n.types.some(t => t.id === type))) &&
      (!query || [n.resource.id, n.resource.label, ...n.types.map(t => t.curie), ...n.values.map(v => v.value)].join(' ').toLocaleLowerCase().includes(query)))
      .sort((a,b) => a.resource.label.localeCompare(b.resource.label));
    el('instances').replaceChildren();
    el('result-count').textContent = matches.length;
    for(const n of matches) {
      const b = element('button', undefined, 'instance' + (n.resource.id === selected ? ' active' : ''));
      b.append(element('strong', n.resource.label), element('small', n.types.map(t => t.curie).join(', ') || (n.external ? 'Externe Referenz' : 'Ohne Typ')));
      b.onclick = () => select(n.resource.id);
      el('instances').append(b);
    }
    if(!matches.length) el('instances').append(element('p', 'Keine passenden Instanzen.', 'empty'));
  }
  function detail(id) {
    const n = resources.get(id), panel = el('details'); panel.replaceChildren();
    if(!n) {panel.append(element('h2','Instanzdetails'), element('p','Keine Instanz ausgewählt.', 'empty')); return;}
    panel.append(element('h2', n.resource.label));
    const iri = element('p', undefined, 'iri'); iri.append(safeLink(n.resource.id, n.resource.id)); panel.append(iri);
    n.types.forEach(t => {const a = safeLink(t.id, t.curie); a.className = 'type'; panel.append(a);});
    if(n.external) panel.append(element('p', 'Referenz ohne Instanzbeschreibung in dieser Datei.', 'empty'));
    const focus = element('button','Nachbarschaft anzeigen','focus-button'); focus.onclick = () => focusOn(id); panel.append(focus);
    panel.append(element('h3', `Datenwerte (${n.values.length})`));
    for(const v of n.values) {const row=element('div',undefined,'detail-row'); row.append(element('span',v.predicate.curie,'predicate'),element('span',v.value)); if(v.language || v.datatype) row.append(element('small',v.language ? '@'+v.language : v.datatype)); panel.append(row);}
    for(const [title, incoming] of [['Ausgehende Beziehungen',false],['Eingehende Beziehungen',true]]) {
      const relations=data.relations.filter(r => (incoming?r.target:r.source)===id); panel.append(element('h3',`${title} (${relations.length})`));
      relations.forEach(r => {const target=resources.get(incoming?r.source:r.target), row=element('div',undefined,'detail-row'); const b=element('button',target.resource.label); b.onclick=()=>select(target.resource.id); row.append(element('span',r.predicate.curie,'predicate'),b); panel.append(row);});
    }
  }
  function select(id) {
    if(!resources.has(id)) return;
    if(!matches.some(n => n.resource.id === id)) {el('search').value='';el('class-filter').value='';list();}
    selected=id; history.replaceState(null,'','#instance='+encodeURIComponent(id)); detail(id); list();
    if(cy) {cy.nodes().unselect(); cy.getElementById(ids.get(id)).select();}
  }
  function focusOn(id) {
    if(!resources.has(id)) return;
    select(id); focusId=id; el('scope').value='focus'; draw();
  }
  function layout() {
    if(!cy || !cy.nodes().length) return;
    cy.layout({name:el('layout').value === 'cose' ? 'fcose' : el('layout').value, animate:false, fit:true, padding:45,
      quality:'proof', nodeDimensionsIncludeLabels:true, nodeRepulsion:()=>9000, idealEdgeLength:()=>110,
      componentSpacing:140, nodeOverlap:30, numIter:2500, randomize:true,
      spacingFactor:1.4, avoidOverlap:true, directed:true, circle:false,
      concentric:n=>n.degree(), levelWidth:()=>2}).run();
  }
  function draw() {
    el('depth-label').hidden=el('scope').value!=='focus';
    if(!cy) return;
    let allowed=new Set(matches.map(n=>n.resource.id));
    if(el('scope').value==='focus' && focusId) {
      const visited=new Set([focusId]); let frontier=[focusId];
      for(let i=0;i<Number(el('depth').value);i++){const next=[]; frontier.forEach(id=>adjacency.get(id).forEach(neighbor=>{if(!visited.has(neighbor)){visited.add(neighbor);next.push(neighbor);}}));frontier=next;}
      allowed=new Set([...allowed].filter(id=>visited.has(id))); allowed.add(focusId);
    }
    const anchor=el('scope').value==='focus'?focusId:selected;
    const ranked=[...allowed].sort((a,b)=>(b===anchor)-(a===anchor) || adjacency.get(b).size-adjacency.get(a).size || a.localeCompare(b));
    const shown=new Set(ranked.slice(0,config.maxNodes)); const elements=[];
    shown.forEach(id=>{const n=resources.get(id); elements.push({data:{id:ids.get(id),label:n.resource.label, ...nodeFace(n),resource:id},classes:n.external?'external':''});});
    data.relations.forEach((r,i)=>{if(shown.has(r.source)&&shown.has(r.target)) elements.push({data:{id:'e'+i,source:ids.get(r.source),target:ids.get(r.target),label:r.predicate.curie}});});
    let literalCount=0, omittedValues=0;
    if(el('literals').checked) shown.forEach(id=>resources.get(id).values.forEach((v,i)=>{
      if(shown.size+literalCount>=config.maxNodes){omittedValues++;return;}
      const lid=ids.get(id)+'v'+i;literalCount++;
      elements.push({data:{id:lid,label:short(v.value+(v.language?' @'+v.language:''),60),color:'#ffffff',owner:id},classes:'literal'}, {data:{id:lid+'e',source:ids.get(id),target:lid,label:v.predicate.curie},classes:'literal-edge'});
    }));
    cy.elements().remove();cy.add(elements);updateLabels();layout();updateLegend();
    if(selected) cy.getElementById(ids.get(selected)).select();
    el('graph-status').textContent=`${shown.size} / ${allowed.size} Ressourcen · ${cy.edges().length} Kanten`+(literalCount?` · ${literalCount} Werte`:'')+(shown.size<allowed.size||omittedValues?` · Anzeigelimit ${config.maxNodes}`:'');
  }
  function updateLabels(){if(cy)cy.style().selector('edge').style('label',el('edge-labels').checked?'data(label)':'').update();}
  list();
  if(typeof cytoscape === 'undefined') {el('graph-status').textContent='Graph-Bibliothek konnte nicht geladen werden. Instanzdaten sind weiterhin verfügbar.';}
  else {
    cy=cytoscape({container:el('graph'),elements:[],minZoom:.05,maxZoom:3,wheelSensitivity:.2,layout:{name:'preset'},style:[
      {selector:'node',style:{shape:'round-rectangle',width:185,height:80,'background-color':'#fff',color:'#202124',label:'','font-size':12,'text-wrap':'wrap','text-max-width':170,'text-valign':'center','text-halign':'center','border-width':1,'border-color':'#0f4449'}},
      {selector:'node[resource]',style:{width:'data(width)',height:'data(height)','background-image':'data(face)','background-fit':'contain','background-width':'100%','background-height':'100%','background-clip':'node','border-color':'data(color)'}},
      {selector:'node.external',style:{'border-color':'#b84a39','border-style':'dashed'}},
      {selector:'node.literal',style:{shape:'rectangle',height:60,label:'data(label)','background-color':'#fff',color:'#0f4449','border-color':'#155c63'}},
      {selector:'edge',style:{width:1.4,'line-color':'#0f4449','target-arrow-color':'#0f4449','target-arrow-shape':'triangle','curve-style':'bezier',label:'data(label)',color:'#202124','font-size':10,'text-rotation':'autorotate','text-background-color':'#fbfcfd','text-background-opacity':.95,'text-background-padding':3,'text-margin-y':-7}},
      {selector:'.literal-edge',style:{'line-style':'dotted','line-color':'#66898c','target-arrow-color':'#66898c',color:'#315e62'}},
      {selector:'node:selected',style:{'border-width':4,'border-color':'#111827'}},
      {selector:'edge:selected',style:{'line-color':'#0f4449','target-arrow-color':'#0f4449',width:3}},
      {selector:'.legend-dim',style:{opacity:.18}}
    ]});
    cy.on('tap','node',event=>{const n=event.target;select(n.data('resource')||n.data('owner'));});
    cy.on('dbltap','node',event=>{const n=event.target;focusOn(n.data('resource')||n.data('owner'));});
    new ResizeObserver(()=>{cy.resize();cy.fit(undefined,40);}).observe(el('graph'));
  }
  el('search').oninput=()=>{list();draw();};el('class-filter').onchange=()=>{list();draw();};
  el('scope').onchange=()=>{if(el('scope').value==='focus')focusId=selected;draw();};
  ['depth','literals'].forEach(id=>el(id).onchange=draw);
  el('layout').onchange=layout;el('relayout').onclick=layout;el('fit').onclick=()=>cy?.fit(undefined,40);
  el('edge-labels').onchange=updateLabels;
  el('zoom-in').onclick=()=>cy?.zoom({level:Math.min(3,cy.zoom()*1.3),renderedPosition:{x:cy.width()/2,y:cy.height()/2}});
  el('zoom-out').onclick=()=>cy?.zoom({level:Math.max(.05,cy.zoom()/1.3),renderedPosition:{x:cy.width()/2,y:cy.height()/2}});
  el('export').onclick=()=>{if(!cy)return;const a=document.createElement('a');a.download=data.title+'-graph.png';a.href=cy.png({full:true,bg:'#ffffff',maxWidth:5000,maxHeight:5000});a.click();};
  function hashSelection(){try {const hash=location.hash;if(hash.startsWith('#instance=')){const id=decodeURIComponent(hash.slice(10));if(resources.has(id)){select(id);return true;}}}catch(_){}return false;}
  draw();
  if(!hashSelection()) {const first=[...data.instances].filter(n=>!n.external).sort((a,b)=>adjacency.get(b.resource.id).size-adjacency.get(a.resource.id).size)[0];if(first){selected=first.resource.id;detail(selected);list();cy?.getElementById(ids.get(selected)).select();}else detail(null);}
  window.addEventListener('hashchange',hashSelection);
  if(window.lucide) lucide.createIcons();
})();
