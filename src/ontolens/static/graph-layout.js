(function (root) {
  "use strict";

  function compactLabel(data, ontologies = []) {
    let label = String(data.label || "");
    if (!["class", "external-class"].includes(data.kind)) return label;
    const namespace = data.ontology;
    if (/^https?:\/\//i.test(label) && namespace && label.startsWith(namespace)) {
      const ontology = ontologies.find(item => item.uri === namespace);
      const prefix = String(ontology?.label || namespace).replace(/[/#]+$/, "").split("/").pop();
      label = `${prefix}:\n${label.slice(namespace.length)}`;
    }
    const parts = label.match(/^([^:\s]+):\s*([^\n]+)$/);
    return parts ? `${parts[1]}:\n${parts[2].replace(/([a-z0-9])([A-Z])/g, "$1 $2")}` : label;
  }

  function networkOptions(count, compact = false) {
    return {
      name: count > 1 ? "fcose" : "grid",
      quality: "proof", randomize: true,
      nodeDimensionsIncludeLabels: true, nodeSeparation: compact ? 60 : 80,
      nodeRepulsion: () => compact ? 6500 : 8500, idealEdgeLength: () => compact ? 170 : 190,
      edgeElasticity: () => 0.45, gravity: 0.25, numIter: 2500,
      tile: true, tilingPaddingHorizontal: compact ? 28 : 60, tilingPaddingVertical: compact ? 28 : 60,
      packComponents: false
    };
  }

  function separateNodes(cy, gap = 24) {
    const nodes = cy.nodes().map(node => {
      const box = node.boundingBox({includeLabels: true, includeOverlays: false});
      const position = node.position();
      return {node, x: position.x, y: position.y, width: box.w, height: box.h};
    }).sort((a, b) => a.node.id().localeCompare(b.node.id()));
    // Resolve residual rectangle collisions without replacing the network layout.
    for (let pass = 0; pass < 100; pass++) {
      let moved = false;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (const b of nodes.slice(i + 1)) {
          const dx = b.x - a.x, dy = b.y - a.y;
          const overlapX = (a.width + b.width) / 2 + gap - Math.abs(dx);
          const overlapY = (a.height + b.height) / 2 + gap - Math.abs(dy);
          if (overlapX <= 0 || overlapY <= 0) continue;
          const axis = overlapX < overlapY ? 'x' : 'y';
          const shift = ((axis === 'x' ? overlapX : overlapY) + .1) / 2;
          const direction = (axis === 'x' ? dx : dy) < 0 ? -1 : 1;
          a[axis] -= shift * direction;
          b[axis] += shift * direction;
          moved = true;
        }
      }
      if (!moved) break;
    }
    nodes.forEach(item => item.node.position({x: item.x, y: item.y}));
  }

  function distributeNodes(cy, width, height) {
    const nodes = cy.nodes().map(node => {
      const box = node.boundingBox({includeLabels: true, includeOverlays: false});
      return {node, ...node.position(), width: box.w, height: box.h};
    });
    if (nodes.length < 6 || width <= 0 || height <= 0) {
      separateNodes(cy);
      return;
    }
    const aspect = Math.max(.5, Math.min(3, width / height));
    const area = nodes.reduce((sum, node) => sum + (node.width + 48) * (node.height + 56), 0);
    const span = {x: Math.sqrt(area * aspect), y: Math.sqrt(area / aspect)};
    // Monotone rank spreading opens dense hubs and pulls sparse outliers inward.
    for (const axis of ['x', 'y']) {
      const ordered = nodes.slice().sort((a, b) => a[axis] - b[axis] || a.node.id().localeCompare(b.node.id()));
      const low = ordered[0][axis], high = ordered[ordered.length - 1][axis];
      ordered.forEach((node, index) => {
        const rank = index / (ordered.length - 1);
        const relative = high > low ? (node[axis] - low) / (high - low) : rank;
        node[axis] = (.8 * rank + .2 * relative - .5) * span[axis];
      });
    }
    nodes.forEach(item => item.node.position({x: item.x, y: item.y}));
    separateNodes(cy, 28);
    const box = cy.nodes().boundingBox({includeLabels: true, includeOverlays: false});
    const stretchX = Math.max(1, aspect * box.h / box.w);
    const stretchY = Math.max(1, box.w / (aspect * box.h));
    const center = {x: (box.x1 + box.x2) / 2, y: (box.y1 + box.y2) / 2};
    cy.nodes().forEach(node => {
      const position = node.position();
      node.position({x: (position.x - center.x) * stretchX, y: (position.y - center.y) * stretchY});
    });
  }

  const api = {compactLabel, networkOptions, separateNodes, distributeNodes};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.OntolensGraphLayout = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
