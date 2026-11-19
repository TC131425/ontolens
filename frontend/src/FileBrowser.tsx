import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowUp, ArrowRight, Folder, FolderPlus, File, Search, X } from 'lucide-react';

type Entry = {name: string; path: string; directory: boolean};
type Listing = {path: string; display_path?: string; parent: string | null; entries: Entry[]};
type Recent = {path: string; label: string};
const suffixes: Record<string, string[]> = {
  project: ['.yaml', '.yml'], html: ['.html', '.htm'], content: ['.md', '.markdown'],
  input: ['.ttl', '.rdf', '.owl', '.nt', '.jsonld', '.json-ld'],
  ontologies: ['.ttl', '.rdf', '.owl', '.nt', '.jsonld', '.json-ld'],
};

function FileBrowser({kind, root, hostDirectory, hostSource, done}: {kind: string; root: string; hostDirectory?: string; hostSource?: string; done: (paths: string[] | null) => void}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const request = useRef<AbortController | null>(null);
  const [listing, setListing] = useState<Listing | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [address, setAddress] = useState(hostDirectory || root);
  const [filter, setFilter] = useState('');
  const [creating, setCreating] = useState(false);
  const [folderName, setFolderName] = useState('');
  const recentKey = `ontolens-recent-folders:${root}:${hostSource || hostDirectory || ''}`;
  const [recent, setRecent] = useState<Recent[]>(() => {
    try {const saved=JSON.parse(localStorage.getItem(recentKey) || '[]');return Array.isArray(saved)?saved.filter((p:Recent)=>typeof p?.path==='string'&&typeof p?.label==='string').slice(0,8):[];} catch {return [];}
  });
  const folderOnly = kind === 'directory' || kind === 'output';
  async function load(path: string) {
    request.current?.abort();
    const controller = new AbortController();request.current=controller;
    setBusy(true);setError('');
    try {
      const response = await fetch('/api/files?path=' + encodeURIComponent(path), {signal:controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Ordner konnte nicht geladen werden.');
      setListing(data);
      setAddress(data.display_path || data.path);setFilter('');setCreating(false);setFolderName('');
      if(kind!=='ontologies') setSelected([]);
    } catch (e) {if(!controller.signal.aborted)setError(e instanceof Error ? e.message : 'Laden fehlgeschlagen');}
    finally {if(!controller.signal.aborted)setBusy(false);}
  }
  useEffect(() => {dialog.current?.showModal();void load(hostDirectory || root);return()=>request.current?.abort();}, []);
  function choose() {
    if(!listing) return;
    const next=[{path:listing.path,label:listing.display_path || listing.path},...recent.filter(item=>item.path!==listing.path)].slice(0,8);
    setRecent(next);try{localStorage.setItem(recentKey,JSON.stringify(next));}catch{/* Storage is optional. */}
    done(folderOnly?[listing.path]:selected);
  }
  async function createFolder() {
    if(!listing) return;
    setBusy(true);setError('');
    try {
      const response=await fetch('/api/files/directory',{method:'POST',headers:{'Content-Type':'application/json','X-Ontolens-Write':'1'},body:JSON.stringify({parent:listing.path,name:folderName})});
      const data=await response.json();
      if(!response.ok) throw new Error(data.detail || 'Ordner konnte nicht angelegt werden.');
      await load(data.path);
    } catch(e) {setError(e instanceof Error?e.message:'Ordner konnte nicht angelegt werden.');}
    finally {setBusy(false);}
  }
  const visible=listing?.entries.filter(entry=>(entry.directory || (!folderOnly && suffixes[kind]?.some(suffix=>entry.name.toLowerCase().endsWith(suffix)))) && entry.name.toLocaleLowerCase().includes(filter.toLocaleLowerCase())) || [];
  const addressChanged=!!listing && address!==(listing.display_path || listing.path);
  return <dialog className="file-browser" ref={dialog} onCancel={e => {e.preventDefault();done(null);}}>
    <div className="file-browser-heading"><h2>{folderOnly ? 'Ordner auswählen' : kind === 'project' ? 'Projekt öffnen' : 'Dateien auswählen'}</h2><button title="Abbrechen" aria-label="Abbrechen" onClick={() => done(null)}><X size={18}/></button></div>
    <form className="file-browser-heading file-browser-address" onSubmit={e=>{e.preventDefault();void load(address);}}><button type="button" title="Übergeordneter Ordner" aria-label="Übergeordneter Ordner" disabled={busy || !listing?.parent} onClick={() => listing?.parent && load(listing.parent)}><ArrowUp size={18}/></button><input aria-label="Ordnerpfad" value={address} disabled={busy} onChange={e=>setAddress(e.target.value)} placeholder="D:\Projekte"/><button title="Pfad öffnen" aria-label="Pfad öffnen" disabled={busy || !address.trim()} type="submit"><ArrowRight size={18}/></button></form>
    {hostDirectory && <div className="file-browser-heading"><button disabled={busy} onClick={()=>void load(hostDirectory)}><Folder size={18}/>Lokales Laufwerk</button><button disabled={busy} onClick={()=>void load(root)}>Gespeicherte Projekte</button></div>}
    <div className="file-browser-tools"><label className="file-browser-search"><Search size={17}/><input type="search" aria-label="Im aktuellen Ordner filtern" placeholder={folderOnly?'Ordner filtern …':'Ordner und Dateien filtern …'} value={filter} onChange={e=>setFilter(e.target.value)}/></label><select aria-label="Zuletzt verwendete Ordner" value="" disabled={busy || !recent.length} onChange={e=>{if(e.target.value)void load(e.target.value);}}><option value="">Zuletzt verwendet</option>{recent.map(item=><option key={item.path} value={item.path}>{item.label}</option>)}</select><button title="Neuen Ordner anlegen" aria-label="Neuen Ordner anlegen" disabled={busy || !listing || addressChanged} onClick={()=>{setCreating(v=>!v);setError('');}}><FolderPlus size={18}/></button></div>
    {creating && <form className="file-browser-heading file-browser-create" onSubmit={e=>{e.preventDefault();void createFolder();}}><input autoFocus aria-label="Neuer Ordnername" placeholder="Ordnername" maxLength={120} value={folderName} disabled={busy} onChange={e=>setFolderName(e.target.value)}/><button type="submit" disabled={busy || !folderName.trim()}>Anlegen</button><button type="button" title="Ordneranlage abbrechen" aria-label="Ordneranlage abbrechen" disabled={busy} onClick={()=>setCreating(false)}><X size={17}/></button></form>}
    {error && <p role="alert">{error}</p>}
    <div className="file-browser-list" aria-busy={busy}>{visible.map(entry => entry.directory ?
      <button key={entry.path} disabled={busy} onClick={() => load(entry.path)}><Folder size={18}/><span>{entry.name}</span></button> :
      <label key={entry.path}><input type={kind === 'ontologies' ? 'checkbox' : 'radio'} name="selected-file" checked={selected.includes(entry.path)} disabled={busy} onChange={e => setSelected(current => kind === 'ontologies' ? e.target.checked ? [...current, entry.path] : current.filter(path => path !== entry.path) : [entry.path])}/><File size={18}/><span>{entry.name}</span></label>)}{!busy&&!visible.length&&<p className="muted">{filter?'Keine passenden Einträge.':'Keine auswählbaren Einträge.'}</p>}</div>
    <div className="file-browser-footer"><span>{folderOnly ? `${visible.length} Ordner` : `${selected.length} ausgewählt`}</span><button onClick={() => done(null)}>Abbrechen</button><button className="primary-action" disabled={busy || !!error || addressChanged || creating || (folderOnly ? !listing : !selected.length)} onClick={choose}>{folderOnly?'Diesen Ordner verwenden':'Auswählen'}</button></div>
  </dialog>;
}

let dialogActive = false;
export function chooseServerFiles(kind: string, root: string, hostDirectory?: string, hostSource?: string): Promise<string[] | null> {
  if (dialogActive) return Promise.reject(new Error('Ein Dateidialog ist bereits geöffnet.'));
  dialogActive = true;
  const container = document.createElement('div');
  document.body.appendChild(container);
  const reactRoot = createRoot(container);
  return new Promise(resolve => {
    reactRoot.render(<FileBrowser kind={kind} root={root} hostDirectory={hostDirectory} hostSource={hostSource} done={paths => {
      resolve(paths);queueMicrotask(() => {reactRoot.unmount();container.remove();dialogActive = false;});
    }}/>);
  });
}
