import { setUiLanguage, useUiLanguage, useText } from './uiLanguage';
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { FolderOpen, Settings, Moon, Sun, RefreshCw, LayoutGrid, Network, Languages } from 'lucide-react';
import { get, isProjectBusy, setProjectBase, type Project, type ExportResult } from './api';
import './style.css';
import { ProjectOverview } from './ProjectOverview';
import { OntologyTable } from './OntologyTable';
import { OntologyDetails } from './OntologyDetails';
import { ExportPreview } from './ExportPreview';
import { ProjectPicker } from './ProjectPicker';
import { ProjectsHome } from './ProjectsHome';
import { PortalSettings } from './PortalSettings';
import { ProjectOntologies } from './ProjectOntologies';

function App() {
  const t = useText();
  const uiLanguage = useUiLanguage();
  useEffect(() => { document.documentElement.lang = uiLanguage; }, [uiLanguage]);
  const [project, setProject] = useState<Project | null>(null);
  const [projectId, setProjectId] = useState('');
  const [optionsDirty, setOptionsDirty] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState('');
  const [page, changePage] = useState<'projects' | 'ontologies' | 'portal' | 'settings'>('projects');
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [contentRevision, setContentRevision] = useState('');
  const [markdownDirty, setMarkdownDirty] = useState(false);
  const [loading, setLoading] = useState(false);
  const [markdownError, setMarkdownError] = useState('');
  const [theme, setTheme] = useState(() => { try { return localStorage.getItem('ontolens-theme') || 'dark'; } catch { return 'dark'; } });
  const [reload, changeReload] = useState(0);
  const [exportMode, setExportMode] = useState<ExportResult['kind']>('reference');
  function confirmDiscard() {if(isProjectBusy()) {window.alert(t('Bitte die laufende Aktion abwarten.'));return false;}return !(markdownDirty || optionsDirty) || window.confirm(t('Ungespeicherte Änderungen verwerfen?'));}
  function switchProject(id: string) {setProjectId(id);setProject(null);setSelected('');setMarkdown(null);setMarkdownDirty(false);setOptionsDirty(false);changePage('ontologies');changeReload(r => r + 1);}
  function selectOntology(id: string) {if (id !== selected && confirmDiscard()) {setMarkdownDirty(false);setOptionsDirty(false);setSelected(id);}}
  function setPage(next: 'projects' | 'ontologies' | 'portal' | 'settings') {if (next !== page && confirmDiscard()) {setMarkdownDirty(false);setOptionsDirty(false);changePage(next);changeReload(r => r + 1);}}
  function setReload(next: React.SetStateAction<number>) {if (confirmDiscard()) {setMarkdownDirty(false);changeReload(next);}}
  useEffect(() => setExportMode('reference'), [selected, reload]);
  useEffect(() => {
    const removed = (event: Event) => {
      if ((event as CustomEvent<string>).detail !== projectId) return;
      setProjectId('');setProject(null);setSelected('');setMarkdown(null);
      setMarkdownDirty(false);setOptionsDirty(false);setProjectBase('');
      setError('');changePage('projects');
      try {localStorage.removeItem('ontolens-project');} catch { /* Optional storage. */ }
    };
    window.addEventListener('ontolens-project-removed', removed);
    return () => window.removeEventListener('ontolens-project-removed', removed);
  }, [projectId]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {if (optionsDirty) {event.preventDefault();event.returnValue = '';}};
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [optionsDirty]);
  useEffect(() => { document.documentElement.dataset.theme = theme; try { localStorage.setItem('ontolens-theme', theme); } catch { /* Storage is optional. */ } }, [theme]);
  useEffect(() => {
    if (!projectId) return;
    const controller = new AbortController(); setError('');
    get<Project>('/api/project', controller.signal).then(p => {setProject(p); setSelected(s => p.ontologies.some(o => o.id === s) ? s : p.ontologies[0]?.id || '');}).catch(e => {if (e.name !== 'AbortError') setError(e.message);});
    return () => controller.abort();
  }, [reload, projectId]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController(); setLoading(true); setMarkdown(null); setMarkdownError('');
    get<{content: string | null; content_revision?: string}>(`/api/ontologies/${encodeURIComponent(selected)}/markdown`, controller.signal).then(r => {setMarkdown(r.content);setContentRevision(r.content_revision || '');setLoading(false);}).catch(e => {if(e.name !== 'AbortError') {setMarkdownError(e.message);setLoading(false);}});
    return () => controller.abort();
  }, [selected, reload, project?.ontologies.find(o => o.id === selected)?.content]);
  const ontology = project?.ontologies.find(o => o.id === selected);
  function updateProject(next: Project) {
    setProject(next);
  }
  return <div className="app">
    <header><strong className="brand">onto<span>lens</span></strong><ProjectPicker activeId={projectId} key={projectId} beforeSwitch={confirmDiscard} onSwitch={switchProject}/><span className="badge">{t("Lokale Entwicklung")}</span>
      <label className="ui-language" title={t("Oberflächensprache")}><Languages size={17} aria-hidden="true"/><select aria-label={t("Oberflächensprache")} value={uiLanguage} onChange={e => setUiLanguage(e.target.value === "en" ? "en" : "de")}><option value="de" lang="de">Deutsch</option><option value="en" lang="en">English</option></select></label>
      <button className="icon" title={t("Daten neu laden")} aria-label={t("Daten neu laden")} onClick={() => setReload(r => r + 1)}><RefreshCw size={18}/></button><button className="icon" title={t("Farbschema wechseln")} aria-label={t("Farbschema wechseln")} onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? <Sun size={18}/> : <Moon size={18}/>}</button></header>
    {error && <div role="alert" className="error">{t(error)} <button onClick={() => setReload(r => r + 1)}>{t("Erneut versuchen")}</button></div>}
    <div className="shell"><nav aria-label={t("Projekt")}><small>{t("ARBEITSBEREICH")}</small><button className={page === 'projects' ? 'active' : ''} onClick={() => setPage('projects')}><LayoutGrid size={18}/>{t("Projekte")}</button><button disabled={!projectId} className={page === 'ontologies' ? 'active' : ''} onClick={() => setPage('ontologies')}><FolderOpen size={18}/>{t("Ontologien")}</button><button disabled={!projectId} className={page === 'portal' ? 'active' : ''} onClick={() => setPage('portal')}><Network size={18}/>Portal</button><button disabled={!projectId} className={page === 'settings' ? 'active' : ''} onClick={() => setPage('settings')}><Settings size={18}/>{t("Projekteinstellungen")}</button><div className="nav-footer">{project?.ontologies.length ?? 0} {t(project?.ontologies.length === 1 ? "Ontologie" : "Ontologien")}<br/>React + FastAPI</div></nav>
    {page === 'projects' ? <ProjectsHome onOpen={switchProject}/> : !project ? <main className="empty">{error ? t("Projekt nicht verfügbar.") : t("Projekt wird geladen …")}</main> : page === 'portal' ? <PortalSettings key={projectId + reload} project={project} onProject={updateProject} onDirty={setOptionsDirty}/> : page === 'settings' ? <main className="settings project-settings"><p className="muted">{project.name}</p><h1>{t("Projekteinstellungen")}</h1><dl><dt>{t("Konfiguration")}</dt><dd>{project.config}</dd><dt>{t("Ausgabeordner")}</dt><dd>{project.output}</dd></dl><ProjectOntologies key={'membership' + projectId + reload} project={project} beforeChange={confirmDiscard} onProject={next => {updateProject(next);setOptionsDirty(false);changeReload(r => r + 1);}}/></main> : <main className="workspace"><section className="configuration"><p className="muted">{project.name}</p><h1>{t("Ontologien")}</h1><ProjectOverview project={project}/><OntologyTable project={project} selected={selected} onSelect={selectOntology}/>
    {ontology && <OntologyDetails onDraftChange={setOptionsDirty} key={projectId + ontology.id + reload} markdownDirty={markdownDirty} ontology={ontology} notices={project.notices ?? []} revision={project.revision} output={project.output} onProject={updateProject} onMode={setExportMode} onExport={result => {setProject(p => p ? {...p, ontologies: p.ontologies.map(o => o.id === ontology.id ? {...o, html: {...o.html, [result.kind]: result}} : o)} : p);setExportMode(result.kind);}} onSaved={(revision, options) => setProject(p => p ? {...p, revision, ontologies: p.ontologies.map(o => o.id === ontology.id ? {...o, options} : o)} : p)}/>}
    </section><ExportPreview key={projectId + selected + reload} mode={exportMode} result={exportMode === 'markdown' ? undefined : ontology?.html?.[exportMode] ?? undefined} markdown={markdown} loading={loading} error={markdownError} ontologyId={selected} projectRevision={project.revision} contentRevision={contentRevision} contentPath={ontology?.content ?? null} onDirty={setMarkdownDirty} onSaved={(content, revision) => {setMarkdown(content);setContentRevision(revision);}}/></main>}
    </div></div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
