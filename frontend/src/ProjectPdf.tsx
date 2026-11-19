import { useEffect, useState } from 'react';
import { Download, FileText } from 'lucide-react';
import { apiFetch, type Project } from './api';

export function ProjectPdf({project, beforeExport}: {project: Project; beforeExport: () => boolean}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [paper, setPaper] = useState('A4');
  const [figures, setFigures] = useState(true);
  const [graph, setGraph] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notices, setNotices] = useState<string[]>([]);
  const [download, setDownload] = useState<{url: string; name: string} | null>(null);
  const documents = project.ontologies.flatMap(ontology => (['reference', 'combined'] as const).map(kind => ({
    key: `${ontology.id}:${kind}`, ontology: ontology.id, kind,
    label: kind === 'reference' ? 'HTML-Dokumentation' : 'HTML + Markdown',
    result: ontology.html?.[kind],
  })));
  useEffect(() => () => {if (download) URL.revokeObjectURL(download.url);}, [download]);
  useEffect(() => {setDownload(null);setNotices([]);setError('');}, [selected, paper, figures, graph, project.revision]);
  async function prepare() {
    if (!beforeExport()) return;
    setBusy(true);setError('');setNotices([]);setDownload(null);
    try {
      const response = await apiFetch('/api/project/pdf', {method:'POST',
        headers:{'Content-Type':'application/json','X-Ontolens-Write':'1'},
        body:JSON.stringify({revision:project.revision, paper, figures, graph,
          documents:documents.filter(item => selected.includes(item.key) && item.result?.available).map(({ontology, kind}) => ({ontology, kind}))})});
      if (!response.ok) {
        const data = await response.json();
        throw new Error(typeof data.detail === 'string' ? data.detail : 'PDF-Export fehlgeschlagen.');
      }
      const blob = await response.blob();
      setNotices(JSON.parse(response.headers.get('X-Ontolens-Notices') || '[]'));
      setDownload({url:URL.createObjectURL(blob), name:response.headers.get('X-Ontolens-Filename') || 'documentation.pdf'});
    } catch(e) {setError(e instanceof Error ? e.message : 'PDF-Export fehlgeschlagen.');}
    finally {setBusy(false);}
  }
  const available = documents.filter(item => item.result?.available);
  const count = available.filter(item => selected.includes(item.key)).length;
  return <section className="project-pdf" aria-labelledby="pdf-export-heading">
    <h3 id="pdf-export-heading">Dokumentation als PDF</h3>
    <fieldset disabled={busy} className="pdf-document-list"><legend>Dokumente</legend>
      {documents.map(item => <label key={item.key} className="pdf-document-choice">
        <input type="checkbox" checked={selected.includes(item.key)} disabled={!item.result?.available}
          onChange={e => setSelected(previous => e.target.checked ? [...previous, item.key] : previous.filter(key => key !== item.key))}/>
        <span><strong>{item.ontology}</strong><span>{item.label}</span></span>
        {!item.result?.available && <small>{item.result ? 'HTML-Datei fehlt' : 'Keine HTML-Datei zugeordnet'}</small>}
      </label>)}
      {!documents.length && <p className="muted">Keine Ontologien im Projekt.</p>}
    </fieldset>
    <div className="pdf-settings"><label>Papierformat<select value={paper} disabled={busy} onChange={e => setPaper(e.target.value)}>
      <option value="A4">A4</option><option value="A3">A3</option></select></label>
      <label className="copy-source-option"><input type="checkbox" checked={figures} disabled={busy} onChange={e => setFigures(e.target.checked)}/>Abbildungen einschließen</label>
      <label className="copy-source-option"><input type="checkbox" checked={graph} disabled={busy} onChange={e => setGraph(e.target.checked)}/>Ontologiegraph ins PDF aufnehmen</label>
    </div>
    <button className="generate-template membership-add" disabled={busy || count === 0 || count > 20} onClick={() => void prepare()}>
      <FileText size={18}/>{busy ? 'PDF wird erstellt …' : `PDF exportieren (${count})`}</button>
    {count > 20 && <p role="alert" className="export-error">Maximal 20 Dokumente pro Export.</p>}
    {error && <p role="alert" className="export-error">{error}</p>}
    {!!notices.length && <details className="project-share-notices" open><summary>PDF-Hinweise ({notices.length})</summary>
      <ul>{notices.map((notice, index) => <li key={index}>{notice}</li>)}</ul></details>}
    {download && <p role="status"><a className="project-download" href={download.url} download={download.name}>
      <Download size={18}/>{download.name.endsWith('.zip') ? 'PDFs als ZIP herunterladen' : 'PDF herunterladen'}</a></p>}
  </section>;
}
