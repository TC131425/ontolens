import { useEffect, useState } from 'react';
import { Download, Package } from 'lucide-react';
import { apiFetch, type Project } from './api';
import { ProjectPdf } from './ProjectPdf';

export function ProjectShare({project, beforeExport}: {project: Project; beforeExport: () => boolean}) {
  const [includeOutputs, setIncludeOutputs] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notices, setNotices] = useState<string[]>([]);
  const [download, setDownload] = useState<{url: string; name: string} | null>(null);
  useEffect(() => () => {if (download) URL.revokeObjectURL(download.url);}, [download]);
  useEffect(() => {setDownload(null);setNotices([]);setError('');}, [project.revision, includeOutputs]);
  async function prepare() {
    if (!beforeExport()) return;
    setBusy(true);setError('');setDownload(null);setNotices([]);
    try {
      const response = await apiFetch('/api/project/archive', {method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Ontolens-Write': '1'},
        body: JSON.stringify({revision: project.revision, include_outputs: includeOutputs})});
      if (!response.ok) {
        const data = await response.json();
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Projekt konnte nicht exportiert werden.');
      }
      const blob = await response.blob();
      setNotices(JSON.parse(response.headers.get('X-Ontolens-Notices') || '[]'));
      const name = (project.name.toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || 'project') + '-project.zip';
      setDownload({url: URL.createObjectURL(blob), name});
    } catch (e) {setError(e instanceof Error ? e.message : 'Export fehlgeschlagen.');}
    finally {setBusy(false);}
  }
  return <section className="project-membership project-share" aria-labelledby="project-share-heading">
    <h2 id="project-share-heading">Projekt weitergeben</h2>
    <label className="copy-source-option"><input type="checkbox" checked={includeOutputs} disabled={busy}
      onChange={e => setIncludeOutputs(e.target.checked)}/>Generierte Dokumentationen und Portale einschließen</label>
    <button className="generate-template membership-add" disabled={busy} onClick={() => void prepare()}>
      <Package size={18}/>{busy ? 'Projektpaket wird geprüft und erstellt …' : 'Projekt als ZIP exportieren'}</button>
    {error && <p className="export-error" role="alert">{error}</p>}
    {!!notices.length && <details className="project-share-notices" open><summary>Exporthinweise ({notices.length})</summary>
      <ul>{notices.map((notice, index) => <li key={index}>{notice}</li>)}</ul></details>}
    {download && <p role="status"><a className="project-download" href={download.url} download={download.name}>
      <Download size={18}/>Projekt-ZIP herunterladen</a></p>}
    <ProjectPdf project={project} beforeExport={beforeExport}/>
  </section>;
}
