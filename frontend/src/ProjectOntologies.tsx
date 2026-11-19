import { useText } from './uiLanguage';
import { useState } from 'react';
import { FolderPlus, Unlink } from 'lucide-react';
import { apiFetch, type Project } from './api';
import { ProjectShare } from './ProjectShare';

export function ProjectOntologies({project, onProject, beforeChange}: {project: Project; onProject: (project: Project) => void; beforeChange: () => boolean}) {
  const t = useText();
  const [copySources, setCopySources] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function request(url: string, body?: object) {
    const response = await apiFetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Ontolens-Write': '1'}, body: JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Projekt konnte nicht geändert werden.');
    return data;
  }
  async function add() {
    if (!beforeChange()) return;
    setBusy(true);setError('');setMessage('');
    try {
      const selection = await request('/api/dialog/ontologies');
      if (!selection.path?.length) return;
      const next = await request('/api/ontologies', {revision: project.revision, paths: selection.path, copy_sources: copySources});
      if (next.revision === project.revision) setMessage('Die ausgewählten Dateien sind bereits zugeordnet.');
      else onProject(next);
    } catch (e) {setError(e instanceof Error ? e.message : 'Hinzufügen fehlgeschlagen');}
    finally {setBusy(false);}
  }
  async function remove(id: string) {
    if (!beforeChange() || !window.confirm(t("{name} aus diesem Projekt entfernen? Quelldateien, Markdown und erzeugte Dokumentationen bleiben erhalten.", {name: id}))) return;
    setBusy(true);setError('');
    try {onProject(await request(`/api/ontologies/${encodeURIComponent(id)}/remove`, {revision: project.revision}));}
    catch (e) {setError(e instanceof Error ? e.message : 'Entfernen fehlgeschlagen');}
    finally {setBusy(false);}
  }
  return <><section className="project-membership" aria-labelledby="membership-heading">
    <h2 id="membership-heading">{t("Ontologien im Projekt")}</h2>
    <ul className="project-inputs">{project.ontologies.map(o => <li key={o.id}><div><strong>{o.id}</strong><small>{o.input}</small></div><button className="icon" title={t("{name} aus Projekt entfernen", {name: o.id})} aria-label={t("{name} aus Projekt entfernen", {name: o.id})} disabled={busy} onClick={() => remove(o.id)}><Unlink size={18}/></button></li>)}</ul>
    {!project.ontologies.length && <p className="muted">{t("Keine Ontologien zugeordnet.")}</p>}
    <label className="copy-source-option"><input type="checkbox" checked={copySources} disabled={busy} onChange={e => setCopySources(e.target.checked)}/>{t("Ontologien und lokale Bilder ins Projekt kopieren")}</label>
    <button className="generate-template membership-add" disabled={busy} onClick={add}><FolderPlus size={18}/>{busy ? t("Bitte warten …") : t("Ontologien hinzufügen")}</button>
    {message && <p className="muted" role="status">{t(message)}</p>}{error && <p role="alert" className="export-error">{t(error)}</p>}
  </section><ProjectShare project={project} beforeExport={beforeChange}/></>;
}
