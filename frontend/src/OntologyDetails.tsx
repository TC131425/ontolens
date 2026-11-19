import { useEffect, useState } from 'react';
import { FolderOpen, FilePlus2, Unlink, FileCode2, FileText, Layers } from 'lucide-react';
import type { Ontology, Project, ExportResult } from './api';
import { ExportNotices } from './ExportNotices';
import { apiFetch } from './api';
import { ThemeSelect } from './ThemeSelect';
import { ontologyNotices } from './ontologyNotices';

export function OntologyDetails({ ontology, notices, revision, output, onSaved, onProject, onExport, onMode, markdownDirty, onDraftChange }: { ontology: Ontology; notices: Project['notices']; revision: string; output: string; onSaved: (revision: string, options: Ontology['options']) => void; onProject: (project: Project) => void; onExport: (result: ExportResult) => void; onMode: (mode: ExportResult['kind']) => void; markdownDirty: boolean; onDraftChange?: (dirty: boolean) => void }) {
  const [tab, setTab] = useState<'settings' | 'markdown' | 'combined'>('settings');
  const keys = ['quality_report', 'recommendations', 'custom_annotations', 'check_content', 'skip_missing_images', 'show_missing_endpoints', 'include_external_classes'] as const;
  const [draft, setDraft] = useState(() => Object.fromEntries(keys.map(k => [k, ontology.options[k] === true])));
  const [theme, setTheme] = useState(String(ontology.options.theme || 'light'));
  const [language, setLanguage] = useState(String(ontology.options.language || ''));
  const [format, setFormat] = useState(String(ontology.options.format || ''));
  const settings = {...draft, theme, language: language.trim() || null, format: format.trim() || null};
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [failed, setFailed] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [markdownProfile, setMarkdownProfile] = useState<'compact' | 'standard'>('standard');
  const dirty = keys.some(k => draft[k] !== (ontology.options[k] === true)) || theme !== (ontology.options.theme || 'light') || language !== (ontology.options.language || '') || format !== (ontology.options.format || '');
  useEffect(() => {onDraftChange?.(dirty);}, [dirty, onDraftChange]);
  async function request(path: string, method: string, body?: object) {
    const response = await apiFetch(path, {method, headers: {'Content-Type': 'application/json', 'X-Ontolens-Write': '1'}, body: body ? JSON.stringify(body) : undefined});
    const result = await response.json();
    if (!response.ok) {
      if (response.status === 409) setConflict(true);
      throw new Error(typeof result.detail === 'string' ? result.detail : 'Aktion fehlgeschlagen');
    }
    return result;
  }
  async function refreshProject() {
    setSaving(true);
    try {
      const project = await request('/api/project', 'GET');
      onProject(project);setConflict(false);setFailed(false);
      setMessage('Projektstand aktualisiert. Deine Auswahl bleibt erhalten. Bitte erneut generieren.');
    } catch (error) {setFailed(true);setMessage(error instanceof Error ? error.message : 'Aktualisieren fehlgeschlagen');}
    finally {setSaving(false);}
  }
  async function choose(kind: 'input' | 'content' | 'output') {
    if (kind === 'content' && markdownDirty && !window.confirm('Ungespeicherte Markdown-Änderungen beim Zuordnen verwerfen?')) return;
    setSaving(true); setFailed(false); setMessage('Dateiauswahl geöffnet …');
    try {
      const result = await request(`/api/dialog/${kind}`, 'POST');
      if (!result.path) {setMessage('Auswahl abgebrochen.'); return;}
      const project = await request(`/api/ontologies/${encodeURIComponent(ontology.id)}/path`, 'PATCH', {revision, kind, path: result.path});
      onProject(project); setMessage(kind === 'output' ? 'Ausgabeordner für das Projekt gespeichert.' : 'Datei zugeordnet.');
    } catch (error) {setFailed(true);setMessage(error instanceof Error ? error.message : 'Auswahl fehlgeschlagen');}
    finally {setSaving(false);}
  }
  async function generateTemplate() {
    setSaving(true); setFailed(false); setMessage('Vorlage wird erzeugt …');
    try {
      let currentRevision = revision;
      if (dirty) {
        const saved = await request(`/api/ontologies/${encodeURIComponent(ontology.id)}/settings`, 'PATCH', {revision, ...settings});
        currentRevision = saved.revision; onSaved(saved.revision, saved.options);
      }
      onProject(await request(`/api/ontologies/${encodeURIComponent(ontology.id)}/template`, 'POST', {revision: currentRevision, profile: markdownProfile}));
      setMessage('Markdown-Vorlage erzeugt und zugeordnet.');
    } catch (error) {setFailed(true);setMessage(error instanceof Error ? error.message : 'Generierung fehlgeschlagen');}
    finally {setSaving(false);}
  }
  async function detachMarkdown() {
    if (!window.confirm('Markdown-Zuordnung entfernen? Die Datei bleibt erhalten. Ungespeicherte Textänderungen werden verworfen.')) return;
    setSaving(true); setFailed(false);
    try {
      onProject(await request(`/api/ontologies/${encodeURIComponent(ontology.id)}/markdown/detach`, 'POST', {revision}));
      setDraft(d => ({...d, check_content: false}));
      setMessage('Markdown entkoppelt. Die Datei bleibt erhalten.');
    } catch (error) {setFailed(true);setMessage(error instanceof Error ? error.message : 'Entkoppeln fehlgeschlagen');}
    finally {setSaving(false);}
  }
  async function save() {
    setSaving(true); setMessage(''); setFailed(false);
    try {
      const response = await apiFetch(`/api/ontologies/${encodeURIComponent(ontology.id)}/settings`, {method: 'PATCH', headers: {'Content-Type': 'application/json', 'X-Ontolens-Write': '1'}, body: JSON.stringify({revision, ...settings})});
      const result = await response.json();
      if (!response.ok) {if (response.status === 409) setConflict(true);throw new Error(typeof result.detail === 'string' ? result.detail : 'Speichern fehlgeschlagen');}
      onSaved(result.revision, result.options); setMessage('In der Projektkonfiguration gespeichert.');
    } catch (error) { setFailed(true); setMessage(error instanceof Error ? error.message : 'Speichern fehlgeschlagen'); }
    finally { setSaving(false); }
  }
  async function exportDocument() {
    setSaving(true); setFailed(false); setMessage('Export wird erzeugt …');
    try {
      let currentRevision = revision;
      if (dirty) {
        const saved = await request(`/api/ontologies/${encodeURIComponent(ontology.id)}/settings`, 'PATCH', {revision, ...settings});
        currentRevision = saved.revision; onSaved(saved.revision, saved.options);
      }
      const result = await request(`/api/ontologies/${encodeURIComponent(ontology.id)}/export`, 'POST', {revision: currentRevision, kind: tab === 'settings' ? 'reference' : tab});
      onExport(result); setMessage('HTML erstellt und verknüpft.');
    } catch (error) {setFailed(true); setMessage(error instanceof Error ? error.message : 'Export fehlgeschlagen');}
    finally {setSaving(false);}
  }
  function changeTab(id: 'settings' | 'markdown' | 'combined') {setTab(id);onMode(id === 'settings' ? 'reference' : id);}
  const htmlKind = tab === 'combined' ? 'combined' : 'reference';
  const linkedHtml = ontology.html?.[htmlKind];
  async function assignHtml(detach = false) {
    if (detach && !window.confirm('HTML-Zuordnung entfernen? Die Datei bleibt erhalten.')) return;
    setSaving(true);setFailed(false);
    try {
      const selected = detach ? {path: null} : await request('/api/dialog/html', 'POST');
      if (!detach && !selected.path) return;
      onProject(await request(`/api/ontologies/${encodeURIComponent(ontology.id)}/html/${htmlKind}`, 'PUT', {revision, path: selected.path}));
      setMessage(detach ? 'HTML entkoppelt. Datei bleibt erhalten.' : 'HTML-Datei zugeordnet.');
    } catch (error) {setFailed(true);setMessage(error instanceof Error ? error.message : 'Zuordnung fehlgeschlagen');}
    finally {setSaving(false);}
  }
  const report = ontologyNotices(ontology, notices);
  const tabs = ['settings', 'markdown', 'combined'] as const;
  return <section className="ontology-details" aria-label={`Details zu ${ontology.id}`}>
    <small className="muted">AUSGEWÄHLTE ONTOLOGIE</small><h2>{ontology.id}</h2>
    <div className="basic-fields common-export-fields">
      <label>Quelldatei<span className="path-picker"><input readOnly value={ontology.input} title={ontology.input}/><button disabled={saving} title="Quelldatei auswählen" aria-label="Quelldatei auswählen" onClick={() => choose('input')}><FolderOpen size={18}/></button></span></label>
      <label>Ausgabeordner<span className="path-picker"><input readOnly value={output} title={output}/><button disabled={saving} title="Ausgabeordner auswählen" aria-label="Ausgabeordner auswählen" onClick={() => choose('output')}><FolderOpen size={18}/></button></span></label>
      <label>Sprache<input disabled={saving} value={language} placeholder="Automatisch" list="label-languages" onChange={e => setLanguage(e.target.value)}/><datalist id="label-languages"><option value="de"/><option value="en"/></datalist></label>
      <label>Parser<input disabled={saving} value={format} placeholder="Automatisch erkennen" list="rdf-formats" onChange={e => setFormat(e.target.value)}/><datalist id="rdf-formats">{['turtle', 'xml', 'nt', 'json-ld'].map(value => <option key={value} value={value}/>)}</datalist></label>
    </div>
    <div className="tabs detail-tabs" role="tablist" aria-label="Ontologiedetails">
      {tabs.map((id, index) => <button disabled={saving} key={id} id={`detail-tab-${id}`} role="tab" aria-controls="detail-export-panel" aria-selected={tab === id} tabIndex={tab === id ? 0 : -1} className={tab === id ? 'active' : ''} onClick={() => changeTab(id)} onKeyDown={e => {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)) return;
        e.preventDefault();
        const next = e.key === 'Home' ? 'settings' : e.key === 'End' ? 'combined' : tabs[(index + (['ArrowRight', 'ArrowDown'].includes(e.key) ? 1 : tabs.length - 1)) % tabs.length];
        changeTab(next); document.getElementById(`detail-tab-${next}`)?.focus();
      }}>{id === 'settings' ? <FileCode2 size={21} aria-hidden="true"/> : id === 'markdown' ? <FileText size={21} aria-hidden="true"/> : <Layers size={21} aria-hidden="true"/>}<span>{id === 'settings' ? 'HTML-Dokumentation' : id === 'markdown' ? 'Markdown' : 'Kombinierte Dokumentation'}</span></button>)}
    </div>
    <div role="tabpanel" id="detail-export-panel" aria-labelledby={`detail-tab-${tab}`}>
    {tab !== 'markdown' && <>
      <fieldset className="basic-options"><legend>Optionen</legend>
        <ThemeSelect value={theme} disabled={saving} onChange={setTheme}/>
        {([['quality_report','Qualitätsbericht'],['recommendations','Metadatenempfehlungen'],['custom_annotations','Custom Annotations'],['skip_missing_images','Fehlende Ontologiebilder überspringen'],['show_missing_endpoints','Platzhalter für fehlende Domain/Range im Graphen'],['include_external_classes','Alle deklarierten externen Klassen im Graphen']] as const).map(([key,label]) => <label key={key}><input type="checkbox" checked={draft[key]} disabled={saving} onChange={e => {const checked = e.currentTarget.checked;setDraft(d => ({...d, [key]: checked}));setMessage('');}}/>{label}</label>)}
      </fieldset>
      <p className="settings-readonly">Diese Optionen gelten für beide HTML-Ausgaben.</p>
    </>}
    {tab === 'combined' && <div className="combined-input"><strong>Markdown-Eingabe</strong><p className="settings-readonly">{ontology.content || 'Keine Markdown-Datei zugeordnet.'}</p>{!ontology.content && <div className="settings-actions"><button disabled={saving} onClick={() => choose('content')}>Datei zuordnen</button><button disabled={saving} onClick={() => changeTab('markdown')}>Vorlage erstellen</button></div>}</div>}
    {tab === 'markdown' && <>
      <div className="markdown-template-settings">
        <label htmlFor="markdown-profile">Vorlagenumfang</label>
        <select id="markdown-profile" disabled={saving || !!ontology.content} value={markdownProfile} onChange={e => setMarkdownProfile(e.target.value as 'compact' | 'standard')}>
          <option value="compact">Kompakt (gekürzt) · 4 Textkapitel</option>
          <option value="standard">Standard · 9 Textkapitel</option>
        </select>
        <p className="settings-readonly">{markdownProfile === 'compact' ? 'Einleitung, Umfang und Anforderungen, konzeptionelles Modell sowie Anwendung und Beispiele.' : 'Zusätzlich: Modellierungsentscheidungen, Interoperabilität, Validierung, Versionierung und Pflege sowie Literatur und Quellen.'}</p>
        {ontology.content ? <p className="settings-readonly">Eine Markdown-Datei ist zugeordnet. Der Vorlagenumfang ist daher deaktiviert und beschreibt nicht den Inhalt dieser Datei.</p> : <button className="generate-template" disabled={saving} onClick={generateTemplate}><FilePlus2 size={17}/>Markdown erzeugen und zuordnen</button>}
      </div>
      <div className="basic-fields markdown-path"><label>Markdown-Datei<span className="path-picker"><input readOnly value={ontology.content || ''} placeholder="Nicht zugeordnet" title={ontology.content || ''}/><button type="button" disabled={saving} title="Markdown-Datei auswählen" aria-label="Markdown-Datei auswählen" onClick={() => choose('content')}><FolderOpen size={18}/></button>{ontology.content && <button type="button" disabled={saving} title="Markdown entkoppeln (Datei behalten)" aria-label="Markdown entkoppeln" onClick={detachMarkdown}><Unlink size={18}/></button>}</span></label></div>
    </>}
      <div className="settings-actions"><button disabled={!dirty || saving} onClick={() => {setDraft(Object.fromEntries(keys.map(k => [k, ontology.options[k] === true])));setTheme(String(ontology.options.theme || 'light'));setLanguage(String(ontology.options.language || ''));setFormat(String(ontology.options.format || ''));setMessage('');}}>Verwerfen</button><button disabled={!dirty || saving} onClick={save}>{saving ? 'Speichert …' : 'Übernehmen'}</button></div>
      {tab !== 'markdown' && <>
        <div className="basic-fields markdown-path"><label>Verknüpfte HTML-Datei<span className="path-picker"><input readOnly value={linkedHtml?.path || ''} placeholder="Nicht zugeordnet" title={linkedHtml?.path}/><button disabled={saving} title="HTML-Datei auswählen" aria-label="HTML-Datei auswählen" onClick={() => assignHtml()}><FolderOpen size={18}/></button>{linkedHtml && <button disabled={saving} title="HTML entkoppeln (Datei behalten)" aria-label="HTML entkoppeln" onClick={() => assignHtml(true)}><Unlink size={18}/></button>}</span></label></div>
        {linkedHtml && <p className="settings-readonly">{linkedHtml.available === false ? 'Die verknüpfte Datei wurde nicht gefunden. Bitte neu zuordnen oder entkoppeln.' : 'Gespeicherte HTML-Ausgabe. Für eine neue Generierung zuerst entkoppeln.'}</p>}
        <button className="export-action" disabled={saving || !!linkedHtml || (tab === 'combined' && (!ontology.content || markdownDirty))} onClick={exportDocument}>{saving ? 'Bitte warten …' : tab === 'settings' ? 'HTML-Dokumentation generieren' : 'Kombinierte Dokumentation generieren'}</button>
      </>}
      {tab === 'combined' && markdownDirty && <p role="status">Bitte zuerst die Markdown-Änderungen speichern.</p>}
      <p className={failed ? 'export-error' : 'settings-readonly'} role={failed ? 'alert' : 'status'}>{message || (dirty ? 'Änderungen werden beim Generieren gespeichert.' : 'Ausgabe im konfigurierten Projektordner.')}</p>
      {conflict && <button disabled={saving} onClick={refreshProject}>Projektstand aktualisieren · Auswahl behalten</button>}
    </div>
    {tab !== 'markdown' && <ExportNotices key={tab} {...report}/>}
  </section>;
}
