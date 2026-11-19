import { useEffect, useState } from 'react';
import { ArrowRight, FolderOpen, FolderPlus, Plus, X, RefreshCw, Trash2 } from 'lucide-react';
import { setProjectBase, appFetch } from './api';

type ProjectEntry = {id: string; path: string; base: string; name: string; count: number; available: boolean};
export function ProjectsHome({onOpen}: {onOpen: (id: string) => void}) {
  const [projects, setProjects] = useState<ProjectEntry[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [directory, setDirectory] = useState('');
  const [files, setFiles] = useState<string[]>([]);
  const [copySources, setCopySources] = useState(true);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function request(path: string, body?: object) {
    const response = await appFetch(path, body ? {method:'POST', headers:{'Content-Type':'application/json','X-Ontolens-Write':'1'}, body:JSON.stringify(body)} : undefined);
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Aktion fehlgeschlagen');
    return data;
  }
  async function refresh() {try {setProjects((await request('/api/projects')).projects);setError('');} catch(e) {setError(e instanceof Error ? e.message : 'Laden fehlgeschlagen');}}
  useEffect(() => {void refresh();}, []);
  function activate(entry: ProjectEntry) {
    setProjectBase(entry.base);
    try {localStorage.setItem('ontolens-project', entry.id);} catch { /* Optional storage. */ }
    onOpen(entry.id);
  }
  async function act(action: () => Promise<void>) {
    setBusy(true);setError('');
    try {await action();} catch(e) {setError(e instanceof Error ? e.message : 'Aktion fehlgeschlagen');}
    finally {setBusy(false);}
  }
  async function remove(entry: ProjectEntry) {
    if (!window.confirm(`Projekt „${entry.name}“ aus der Projektliste löschen?\n\nDateien, Ontologien, Bilder und Exporte bleiben erhalten. Über „Projekt öffnen“ kannst du es erneut hinzufügen.\n\n${entry.path}`)) return;
    await act(async () => {
      const response = await appFetch(`/api/projects/${encodeURIComponent(entry.id)}`, {method: 'DELETE', headers: {'X-Ontolens-Write': '1'}});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Löschen fehlgeschlagen');
      setProjects(previous => previous.filter(p => p.id !== entry.id));
      window.dispatchEvent(new CustomEvent('ontolens-project-removed', {detail: entry.id}));
    });
  }
  const visible = projects.filter(p => `${p.name} ${p.path}`.toLowerCase().includes(search.toLowerCase()));
  return <main className="projects-home">
    <div className="projects-heading"><div><p className="muted">ARBEITSBEREICH</p><h1>Projekte</h1></div><div className="projects-actions">
      <button disabled={busy} onClick={() => act(async () => {const data = await request('/api/projects/open', {});if(data.project) activate(data.project);})}><FolderOpen size={18}/>Projekt öffnen</button>
      <button className="primary-action" disabled={busy} onClick={() => setCreating(true)}><FolderPlus size={18}/>Neues Projekt</button>
    </div></div>
    {error && <p className="export-error" role="alert">{error}</p>}
    {creating && <section className="new-project" aria-label="Neues Projekt">
      <div className="projects-heading"><h2>Neues Projekt</h2><button className="icon" title="Abbrechen" aria-label="Neues Projekt abbrechen" disabled={busy} onClick={() => setCreating(false)}><X size={18}/></button></div>
      <form onSubmit={event => {event.preventDefault();void act(async () => {const data = await request('/api/projects', {name, directory, ontologies:files, copy_sources:copySources});activate(data.project);});}}>
        <div className="new-project-fields"><label>Projektname<input autoFocus required maxLength={120} value={name} disabled={busy} onChange={e => setName(e.target.value)}/></label>
        <label>Speicherordner<span className="path-picker"><input readOnly required value={directory} placeholder="Ordner auswählen"/><button type="button" aria-label="Projektordner auswählen" title="Projektordner auswählen" disabled={busy} onClick={() => act(async () => {const data = await request('/api/projects/dialog/directory', {});if(data.path) setDirectory(data.path);})}><FolderOpen size={18}/></button></span></label></div>
        <div className="projects-heading"><h3>Ontologien ({files.length})</h3><button type="button" disabled={busy} onClick={() => act(async () => {const data = await request('/api/projects/dialog/ontologies', {});setFiles(previous => [...new Set([...previous, ...data.paths as string[]])]);})}><Plus size={17}/>Dateien hinzufügen</button></div>
        <ul className="project-inputs">{files.map(file => <li key={file}><div><strong>{file.split(/[\\/]/).pop()}</strong><small>{file}</small></div><button type="button" className="icon" title="Aus Auswahl entfernen" aria-label={`${file.split(/[\\/]/).pop()} entfernen`} disabled={busy} onClick={() => setFiles(previous => previous.filter(p => p !== file))}><X size={16}/></button></li>)}</ul>
        {!files.length && <p className="muted">Noch keine Ontologien ausgewählt.</p>}
        <label className="copy-source-option"><input type="checkbox" checked={copySources} disabled={busy} onChange={e => setCopySources(e.target.checked)}/>Ontologien und lokale Bilder ins Projekt kopieren</label>
        <p className="muted">{copySources ? 'Eigenständiger Projektordner mit relativen Pfaden. Originaldateien bleiben unverändert. Externe Bild-URLs bleiben online.' : 'Quelldateien werden nur verknüpft. Nach dem Verschieben sind diese Pfade möglicherweise nicht mehr erreichbar.'}</p>
        <div className="projects-actions"><button className="primary-action" disabled={busy || !name.trim() || !directory || !files.length} type="submit"><FolderPlus size={18}/>{busy ? 'Bitte warten …' : 'Projekt erstellen'}</button></div>
      </form>
    </section>}
    <div className="projects-search"><input type="search" aria-label="Projekte suchen" placeholder="Projekte suchen …" value={search} onChange={e => setSearch(e.target.value)}/><span>{visible.length} Projekte</span><button className="icon" title="Projektliste aktualisieren" aria-label="Projektliste aktualisieren" disabled={busy} onClick={refresh}><RefreshCw size={17}/></button></div>
    <div className="projects-list">{visible.map(entry => <article key={entry.id} className="project-row"><FolderOpen size={25}/><div><h2>{entry.name}</h2><p>{entry.available ? `${entry.count} Ontologien` : 'Projekt nicht verfügbar'}</p><small title={entry.path}>{entry.path}</small></div><button className="icon" title={`${entry.name} öffnen`} aria-label={`${entry.name} öffnen`} disabled={busy || !entry.available} onClick={() => activate(entry)}><ArrowRight size={20}/></button><button className="icon" title="Aus Projektliste löschen (Dateien behalten)" aria-label={`${entry.name} aus Projektliste löschen`} disabled={busy} onClick={() => void remove(entry)}><Trash2 size={18}/></button></article>)}</div>
    {!visible.length && <p className="muted">Keine Projekte gefunden.</p>}
  </main>;
}
