import { useText } from './uiLanguage';
import { useEffect, useState } from 'react';
import { ArrowRight, FolderOpen, FolderPlus, Plus, X, RefreshCw, Trash2 } from 'lucide-react';
import { setProjectBase, appFetch } from './api';

type ProjectEntry = {id: string; path: string; base: string; name: string; count: number; available: boolean};
export function ProjectsHome({onOpen}: {onOpen: (id: string) => void}) {
  const t = useText();
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
    if (!window.confirm(t("Projekt „{name}“ aus der Projektliste löschen?\n\nDateien, Ontologien, Bilder und Exporte bleiben erhalten. Über „Projekt öffnen“ kannst du es erneut hinzufügen.\n\n{path}", {name: entry.name, path: entry.path}))) return;
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
    <div className="projects-heading"><div><p className="muted">{t("ARBEITSBEREICH")}</p><h1>{t("Projekte")}</h1></div><div className="projects-actions">
      <button disabled={busy} onClick={() => act(async () => {const data = await request('/api/projects/open', {});if(data.project) activate(data.project);})}><FolderOpen size={18}/>{t("Projekt öffnen")}</button>
      <button className="primary-action" disabled={busy} onClick={() => setCreating(true)}><FolderPlus size={18}/>{t("Neues Projekt")}</button>
    </div></div>
    {error && <p className="export-error" role="alert">{t(error)}</p>}
    {creating && <section className="new-project" aria-label={t("Neues Projekt")}>
      <div className="projects-heading"><h2>{t("Neues Projekt")}</h2><button className="icon" title={t("Abbrechen")} aria-label={t("Neues Projekt abbrechen")} disabled={busy} onClick={() => setCreating(false)}><X size={18}/></button></div>
      <form onSubmit={event => {event.preventDefault();void act(async () => {const data = await request('/api/projects', {name, directory, ontologies:files, copy_sources:copySources});activate(data.project);});}}>
        <div className="new-project-fields"><label>{t("Projektname")}<input autoFocus required maxLength={120} value={name} disabled={busy} onChange={e => setName(e.target.value)}/></label>
        <label>{t("Speicherordner")}<span className="path-picker"><input readOnly required value={directory} placeholder={t("Ordner auswählen")}/><button type="button" aria-label={t("Projektordner auswählen")} title={t("Projektordner auswählen")} disabled={busy} onClick={() => act(async () => {const data = await request('/api/projects/dialog/directory', {});if(data.path) setDirectory(data.path);})}><FolderOpen size={18}/></button></span></label></div>
        <div className="projects-heading"><h3>{t("Ontologien (")}{files.length})</h3><button type="button" disabled={busy} onClick={() => act(async () => {const data = await request('/api/projects/dialog/ontologies', {});setFiles(previous => [...new Set([...previous, ...data.paths as string[]])]);})}><Plus size={17}/>{t("Dateien hinzufügen")}</button></div>
        <ul className="project-inputs">{files.map(file => <li key={file}><div><strong>{file.split(/[\\/]/).pop()}</strong><small>{file}</small></div><button type="button" className="icon" title={t("Aus Auswahl entfernen")} aria-label={t("{name} entfernen", {name: file.split(/[\\/]/).pop()})} disabled={busy} onClick={() => setFiles(previous => previous.filter(p => p !== file))}><X size={16}/></button></li>)}</ul>
        {!files.length && <p className="muted">{t("Noch keine Ontologien ausgewählt.")}</p>}
        <label className="copy-source-option"><input type="checkbox" checked={copySources} disabled={busy} onChange={e => setCopySources(e.target.checked)}/>{t("Ontologien und lokale Bilder ins Projekt kopieren")}</label>
        <p className="muted">{copySources ? t("Eigenständiger Projektordner mit relativen Pfaden. Originaldateien bleiben unverändert. Externe Bild-URLs bleiben online.") : t("Quelldateien werden nur verknüpft. Nach dem Verschieben sind diese Pfade möglicherweise nicht mehr erreichbar.")}</p>
        <div className="projects-actions"><button className="primary-action" disabled={busy || !name.trim() || !directory || !files.length} type="submit"><FolderPlus size={18}/>{busy ? t("Bitte warten …") : t("Projekt erstellen")}</button></div>
      </form>
    </section>}
    <div className="projects-search"><input type="search" aria-label={t("Projekte suchen")} placeholder={t("Projekte suchen …")} value={search} onChange={e => setSearch(e.target.value)}/><span>{visible.length} {t(visible.length === 1 ? "Projekt" : "Projekte")}</span><button className="icon" title={t("Projektliste aktualisieren")} aria-label={t("Projektliste aktualisieren")} disabled={busy} onClick={refresh}><RefreshCw size={17}/></button></div>
    <div className="projects-list">{visible.map(entry => <article key={entry.id} className="project-row"><FolderOpen size={25}/><div><h2>{entry.name}</h2><p>{entry.available ? `${entry.count} ${t(entry.count === 1 ? "Ontologie" : "Ontologien")}` : t("Projekt nicht verfügbar")}</p><small title={entry.path}>{entry.path}</small></div><button className="icon" title={t("{name} öffnen", {name: entry.name})} aria-label={t("{name} öffnen", {name: entry.name})} disabled={busy || !entry.available} onClick={() => activate(entry)}><ArrowRight size={20}/></button><button className="icon" title={t("Aus Projektliste löschen (Dateien behalten)")} aria-label={t("{name} aus Projektliste löschen", {name: entry.name})} disabled={busy} onClick={() => void remove(entry)}><Trash2 size={18}/></button></article>)}</div>
    {!visible.length && <p className="muted">{t("Keine Projekte gefunden.")}</p>}
  </main>;
}
