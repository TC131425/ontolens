import { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import type { Project } from './api';
import { ontologyNotices } from './ontologyNotices';

export function OntologyTable({ project, selected, onSelect }: {
  project: Project; selected: string; onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState('');
  const filename = (path: string) => path.split(/[\\/]/).pop() || path;
  const entries = project.ontologies.filter(o =>
    `${o.id} ${filename(o.input)}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  return <section aria-label="Ontologien auswählen" className="ontology-table-section">
    <div className="ontology-table-toolbar">
      <input type="search" aria-label="Ontologie suchen" placeholder="Ontologie suchen …" value={query} onChange={e => setQuery(e.target.value)}/>
      <span aria-live="polite">{entries.length} {entries.length === 1 ? 'Eintrag' : 'Einträge'}</span>
    </div>
    <table className="ontology-table">
      <thead><tr><th scope="col">Ontologie</th><th scope="col">Prüfhinweise</th><th scope="col"><span className="sr-only">Auswahl</span></th></tr></thead>
      <tbody>{entries.map(o => {
        const report = ontologyNotices(o, project.notices ?? []);
        const notices = report.notices;
        return <tr key={o.id} className={o.id === selected ? 'selected-row' : ''}>
          <td><button className="ontology-name" aria-pressed={o.id === selected} onClick={() => onSelect(o.id)}>{o.id}</button><small>{filename(o.input)}</small></td>
          <td><span className={`table-status ${notices.length ? 'warning' : report.generated ? 'clear' : 'muted'}`} title={report.context}>{notices.length ? `${notices.length} ${notices.length === 1 ? 'Hinweis' : 'Hinweise'}` : report.generated ? 'Keine Hinweise' : 'Noch nicht geprüft'}</span></td>
          <td><button className="table-select" title={`${o.id} auswählen`} aria-label={`${o.id} auswählen`} aria-pressed={o.id === selected} onClick={() => onSelect(o.id)}><ArrowRight size={17}/></button></td>
        </tr>;
      })}{entries.length === 0 && <tr><td colSpan={3} className="table-empty">Keine Ontologie gefunden.</td></tr>}</tbody>
    </table>
  </section>;
}
