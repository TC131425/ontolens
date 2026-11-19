import { useText } from './uiLanguage';
import { useEffect, useState } from 'react';
import { Download, ExternalLink, Network, FileText, FolderOpen, Unlink } from 'lucide-react';
import { apiFetch, type Project } from './api';
import { ExportNotices } from './ExportNotices';
import { ThemeSelect, VariantSelect } from './ThemeSelect';

export function PortalSettings({project, onProject, onDirty}: {project: Project; onProject: (project: Project) => void; onDirty: (dirty: boolean) => void}) {
  const t = useText();
  const initialSelection = (project.portal.selection ?? project.ontologies.map(o => o.id)).filter(id => project.ontologies.some(o => o.id === id));
  const [selection, setSelection] = useState(() => initialSelection.filter(id => project.ontologies.some(o => o.id === id)));
  const [title, setTitle] = useState(project.portal.last_title || project.portal.title);
  const [theme, setTheme] = useState(project.portal.theme || 'light');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [variant, setVariant] = useState('light');
  const linked = project.portal.result;
  const result = linked ? {...linked, ...linked.variants?.[variant]} : linked;
  const dirty = title !== (project.portal.last_title || project.portal.title) || JSON.stringify(selection) !== JSON.stringify(initialSelection) || theme !== (project.portal.theme || 'light');
  useEffect(() => {onDirty(dirty);}, [dirty, onDirty]);
  async function generate() {
    setBusy(true);setError('');setMessage('Portal wird generiert …');
    try {
      const response = await apiFetch('/api/portal/export', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Ontolens-Write': '1'}, body: JSON.stringify({revision: project.revision, title, ontologies: selection, theme})});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Portal konnte nicht erstellt werden.');
      onProject(data);setTitle(data.portal.last_title);setMessage('Portal erstellt.');
    } catch (e) {setError(e instanceof Error ? e.message : 'Generierung fehlgeschlagen');setMessage('');}
    finally {setBusy(false);}
  }
  async function assign(detach = false) {
    if (detach && !window.confirm(t('Portal-Zuordnung lösen? Alle Dateien bleiben erhalten.'))) return;
    setBusy(true);setError('');setMessage('');
    try {
      let path = null;
      if (!detach) {
        const response = await apiFetch('/api/dialog/html', {method: 'POST', headers: {'X-Ontolens-Write': '1'}});
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Dateiauswahl fehlgeschlagen');
        if (!data.path) return;
        path = data.path;
      }
      const response = await apiFetch('/api/portal/html', {method: 'PUT', headers: {'Content-Type': 'application/json', 'X-Ontolens-Write': '1'}, body: JSON.stringify({revision: project.revision, path})});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Zuordnung fehlgeschlagen');
      onProject(data);setMessage(detach ? 'Portal entkoppelt. Dateien bleiben erhalten.' : 'Portal verknüpft.');
    } catch (e) {setError(e instanceof Error ? e.message : 'Zuordnung fehlgeschlagen');}
    finally {setBusy(false);}
  }
  return <main className="workspace portal-workspace" aria-labelledby="portal-heading">
    <section className="configuration">
    <p className="muted">{project.name}</p><h1 id="portal-heading">Portal</h1>
    <div className="basic-fields"><label>{t("Portaltitel")}<input value={title} maxLength={200} disabled={busy} onChange={e => setTitle(e.target.value)}/></label></div>
    <fieldset className="portal-selection" disabled={busy}><legend>{t("Enthaltene Ontologien ·")} {selection.length} / {project.ontologies.length}</legend>
      <label className="portal-select-all"><input type="checkbox" disabled={!project.ontologies.length} checked={project.ontologies.length > 0 && selection.length === project.ontologies.length} onChange={e => setSelection(e.target.checked ? project.ontologies.map(o => o.id) : [])}/>{t("Alle auswählen")}</label>
      {project.ontologies.map(o => <label key={o.id}><input type="checkbox" checked={selection.includes(o.id)} onChange={e => setSelection(ids => e.target.checked ? project.ontologies.filter(item => item.id === o.id || ids.includes(item.id)).map(item => item.id) : ids.filter(id => id !== o.id))}/><span><strong>{o.id}</strong><small>{o.input.split(/[\\/]/).pop()}</small></span><span className="muted">{o.content ? 'HTML + Markdown' : t("HTML-Dokumentation")}</span></label>)}
    </fieldset>
    {!project.ontologies.length && <p className="muted">{t("Keine Ontologien im Projekt.")}</p>}
    <fieldset className="basic-options"><legend>{t("Portal und Dokumentationen")}</legend><ThemeSelect value={theme} disabled={busy} onChange={setTheme}/></fieldset>
    <div className="basic-fields markdown-path"><label>{t("Verknüpfte Portaldatei")}<span className="path-picker"><input readOnly value={result?.path || ''} placeholder={t("Nicht zugeordnet")} title={result?.path}/><button disabled={busy} title={t("Portaldatei auswählen (index.html)")} aria-label={t("Portaldatei auswählen")} onClick={() => assign()}><FolderOpen size={18}/></button>{result && <button disabled={busy} title={t("Portal entkoppeln (Dateien behalten)")} aria-label={t("Portal entkoppeln")} onClick={() => assign(true)}><Unlink size={18}/></button>}</span></label></div>
    {result && <p className="settings-readonly">{t("Für eine neue Generierung zuerst die Portal-Zuordnung lösen.")}</p>}
    <button className="export-action" disabled={busy || !!result || !selection.length || !title.trim()} onClick={generate}><Network size={18}/>{busy ? t("Generiert …") : t("Portal generieren")}</button>
    <p role="status" className="muted">{t(message)}</p>
    {error && <p role="alert" className="export-error">{t(error)}</p>}
    {result && <ExportNotices notices={result.notices} generated/>}
    </section>
    <section className="document portal-preview" aria-label={t("Portalvorschau")} aria-busy={busy}>
      <div className="document-header"><strong>{t("Portalvorschau")}</strong>
        {result?.variants?.dark && <VariantSelect value={variant} onChange={setVariant}/>}
        {result && result.available !== false && <div className="portal-preview-actions"><a href={result.preview} target="_blank" rel="noreferrer"><ExternalLink size={16}/>{t("Öffnen")}</a><a href={result.download}><Download size={16}/>{t(result.downloadLabel || "Herunterladen")}</a></div>}
        {result && <details className="document-location"><summary><FileText size={15}/><span>{result.path.split(/[\\/]/).pop()}</span></summary><div>{result.path}</div></details>}
      </div>
      {dirty && result && <p className="portal-preview-state" role="status">{t("Vorschau des letzten Builds · Auswahl noch nicht generiert")}</p>}
      {result?.available !== false && result ? <iframe className="html-export-preview" title={t("Ontologieportal Vorschau")} src={result.preview} sandbox="allow-scripts allow-downloads"/> : <p className="empty" role="status">{result ? t("Die verknüpfte Portaldatei wurde nicht gefunden.") : t("Noch kein Portal generiert.")}</p>}
    </section>
  </main>;
}
