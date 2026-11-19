export const markdownSlots = [
  {id: 'metadata', label: 'Metadaten und Mitwirkende'},
  {id: 'figures', label: 'Abbildungen'},
  {id: 'quality-report', label: 'Qualit\u00e4tsbericht'},
  {id: 'prefixes', label: 'Namensraum-Pr\u00e4fixe'},
  {id: 'used-ontologies', label: 'Verwendete Ontologien'},
  {id: 'downloads', label: 'Downloads'},
  {id: 'visualization', label: 'Graph'},
  {id: 'overview', label: '\u00dcbersicht'},
  {id: 'cross-reference', label: 'Technische Referenz'},
] as const;

const slotAliases: Record<string, string> = {namespaces: 'prefixes', 'namespace-prefixes': 'prefixes', quality: 'quality-report'};

export function usedMarkdownSlots(text: string) {
  const used = new Set<string>();
  // Match the standalone slot comments accepted by the HTML generator.
  for (const match of text.matchAll(/^\s*<!--\s*ontolens:([a-z0-9_-]+)\s*-->\s*$/gmi)) {
    const id = match[1].toLowerCase();
    used.add(slotAliases[id] ?? id);
  }
  return used;
}

export function markdownImage(path: string, alt: string) {
  const destination = path.trim().replace(/\\/g, '/').replace(/[<>\r\n]/g, character => encodeURIComponent(character));
  if (!destination) throw new Error('Bitte einen Bildpfad oder eine URL angeben.');
  const description = alt.replace(/[\r\n]+/g, ' ').replace(/[\\\[\]]/g, '\\$&');
  return `![${description}](<${destination}>)`;
}

export function markdownLink(url: string, label: string) {
  const target = url.trim();
  if (!target) throw new Error('Bitte ein Linkziel angeben.');
  let parsed: URL;
  try {parsed = new URL(target, 'https://ontolens.invalid/');}
  catch {throw new Error('Bitte ein g\u00fcltiges Linkziel angeben.');}
  if (!['http:', 'https:', 'mailto:'].includes(parsed.protocol) || /[\u0000-\u001f\u007f]/.test(target)) {
    throw new Error('Erlaubt sind http/https, mailto und relative Links wie #cross-reference.');
  }
  const destination = target.replace(/\\/g, '/').replace(/[<> ]/g, character => encodeURIComponent(character));
  const text = (label.trim() || target).replace(/[\r\n]+/g, ' ').replace(/[\\`*_\[\]<>]/g, '\\$&');
  return `[${text}](<${destination}>)`;
}

export function markdownTable(columns: number, rows: number) {
  if (!Number.isInteger(columns) || columns < 1 || columns > 10 || !Number.isInteger(rows) || rows < 1 || rows > 50) {
    throw new Error('Bitte 1 bis 10 Spalten und 1 bis 50 Datenzeilen angeben.');
  }
  const line = (cells: string[]) => `| ${cells.join(' | ')} |`;
  return [line(Array.from({length: columns}, (_, index) => `Spalte ${index + 1}`)),
    line(Array(columns).fill('---')),
    ...Array.from({length: rows}, () => line(Array(columns).fill('Wert')))].join('\n');
}

export function insertMarkdownBlock(text: string, block: string, start = text.length, end = start) {
  start = Math.max(0, Math.min(text.length, start));
  end = Math.max(start, Math.min(text.length, end));
  const before = text.slice(0, start), after = text.slice(end);
  const prefix = !before || before.endsWith('\n\n') ? '' : before.endsWith('\n') ? '\n' : '\n\n';
  const suffix = after.startsWith('\n\n') ? '' : !after || after.startsWith('\n') ? '\n' : '\n\n';
  const replacement = prefix + block + suffix;
  return {text: before + replacement + after, replacement, start, end, cursor: start + replacement.length};
}

export function insertMarkdownInline(text: string, replacement: string, start = text.length, end = start) {
  start = Math.max(0, Math.min(text.length, start));
  end = Math.max(start, Math.min(text.length, end));
  return {text: text.slice(0, start) + replacement + text.slice(end), replacement, start, end, cursor: start + replacement.length};
}
