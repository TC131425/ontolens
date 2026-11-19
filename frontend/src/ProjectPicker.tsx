import { useEffect, useState } from 'react';
import { FolderOpen } from 'lucide-react';
import { setProjectBase, appFetch } from './api';

type Entry = {id: string; path: string; base: string; name: string; count: number; available: boolean};
export function ProjectPicker({beforeSwitch, onSwitch, activeId}: {beforeSwitch: () => boolean; onSwitch: (id: string) => void; activeId: string}) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [selected, setSelected] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function load() {
    const response = await fetch('/api/projects');
    if (!response.ok) throw new Error('Projektliste konnte nicht geladen werden.');
    const data = await response.json();setEntries(data.projects);return data;
  }
  function activate(entry: Entry) {
    setProjectBase(entry.base);setSelected(entry.id);
    try {localStorage.setItem('ontolens-project', entry.id);} catch { /* Optional storage. */ }
    onSwitch(entry.id);
  }
  useEffect(() => {
    const refresh = () => {void load().catch(e => setError(e.message));};
    window.addEventListener('ontolens-project-removed', refresh);
    return () => window.removeEventListener('ontolens-project-removed', refresh);
  }, []);
  useEffect(() => {let active = true;load().then(data => {
    if (!active) return;
    const entry = data.projects.find((p: Entry) => p.id === activeId);
    if (entry) setSelected(entry.id);
  }).catch(e => {if(active) setError(e.message);});return () => {active = false;};}, []);
  async function open() {
    if (!beforeSwitch()) return;
    setBusy(true);setError('');
    try {
      const response = await appFetch('/api/projects/open', {method:'POST', headers:{'X-Ontolens-Write':'1'}});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Öffnen fehlgeschlagen');
      const list = await load();
      if (data.project) activate(list.projects.find((p: Entry) => p.id === data.project.id));
    } catch(e) {setError(e instanceof Error ? e.message : 'Öffnen fehlgeschlagen');}
    finally {setBusy(false);}
  }
  return <div className="project-picker"><label className="sr-only" htmlFor="project-select">Projekt auswählen</label>
    <select id="project-select" title={entries.find(p => p.id === selected)?.path} disabled={busy} value={selected} onChange={e => {const entry = entries.find(p => p.id === e.target.value);if(entry && beforeSwitch()) activate(entry);}}>
      <option value="" disabled>{entries.length ? 'Projekt auswählen' : 'Keine Projekte'}</option>
      {entries.map(entry => <option value={entry.id} key={entry.id} disabled={!entry.available}>{entry.name} · {entry.count} Ontologien{entry.available ? '' : ' · Nicht verfügbar'}</option>)}
    </select><button className="icon" title="Projekt öffnen (YAML)" aria-label="Projekt öffnen" disabled={busy} onClick={open}><FolderOpen size={18}/></button>
    {error && <span className="project-picker-error" role="alert">{error}</span>}
  </div>;
}
