import { ChevronRight, ClipboardCheck, Info } from 'lucide-react';

const metadataLabels: Record<string, string> = {
  'Previous version': 'Vorherige Version', 'Version IRI': 'Versions-IRI',
  Citation: 'Zitiervorschlag', Abstract: 'Kurzfassung', 'See also': 'Weiterführende Links',
  Status: 'Status', 'Backward compatibility': 'Abwärtskompatibilität',
  Incompatibility: 'Inkompatibilität', DOI: 'DOI', Logo: 'Logo', Diagram: 'Diagramm',
  License: 'Lizenz', Creator: 'Erstellende', Contributor: 'Mitwirkende',
  'Creation date': 'Erstellungsdatum', 'Namespace URI': 'Namensraum-URI',
  Prefix: 'Präfix', Title: 'Titel', Description: 'Beschreibung',
  'Modification Date': 'Änderungsdatum', 'Issued date': 'Veröffentlichungsdatum',
  Source: 'Quelle', Publisher: 'Herausgeber',
};

// Interpret the generator's existing message format; unknown notices remain intact.
export function formatNotice(message: string) {
  const metadata = message.match(/^Missing (recommended|optional) metadata: (.+)$/);
  if (metadata) return {group: 'Metadaten', subject: metadataLabels[metadata[2]] || metadata[2],
    detail: 'Nicht angegeben', priority: metadata[1] === 'recommended' ? 'Empfohlen' : 'Optional'};
  const term = message.match(/^(.+) has no (label|comment|domain|range)$/);
  if (term) {
    const labels: Record<string, string> = {label: 'Label fehlt', comment: 'Beschreibung fehlt', domain: 'Domain fehlt', range: 'Range fehlt'};
    return {group: term[2] === 'label' ? 'Labels' : term[2] === 'comment' ? 'Beschreibungen' : 'Domain und Range',
      subject: term[1], detail: labels[term[2]], priority: ''};
  }
  if (/^Abbildung (übersprungen|fehlt): /.test(message)) return {group: 'Abbildungen', subject: message.slice(message.indexOf(': ') + 2), detail: 'Datei nicht gefunden', priority: ''};
  const chapter = message.match(/^(.+): (missing|empty)$/);
  if (chapter) return {group: 'Markdown-Kapitel', subject: chapter[1], detail: chapter[2] === 'missing' ? 'Kapitel fehlt' : 'Kapitel ist leer', priority: ''};
  return {group: 'Weitere Hinweise', subject: message, detail: '', priority: ''};
}

export function ExportNotices({notices, generated, context, emptyMessage}: {notices: string[]; generated: boolean; context?: string; emptyMessage?: string}) {
  const groups = new Map<string, ReturnType<typeof formatNotice>[]>();
  for (const message of notices) {
    const notice = formatNotice(message);
    groups.set(notice.group, [...(groups.get(notice.group) || []), notice]);
  }
  return <section className="generation-notices" aria-label="Prüfhinweise">
    <div className="generation-notices-heading"><ClipboardCheck size={18}/><h3>Prüfhinweise</h3><span className="notice-count">{notices.length}</span></div>
    <p className="notice-context">{context ?? (generated ? 'Ergebnis der letzten Generierung' : 'Projektübersicht · Noch keine Generierung geprüft')}</p>
    {!notices.length && <p className="notice-empty"><Info size={16}/>{emptyMessage ?? (generated ? 'Keine Hinweise aus den aktivierten Prüfungen.' : 'Keine Hinweise aus der Projektübersicht.')}</p>}
    {[...groups].map(([group, items]) => <details className="notice-group" key={group}>
      <summary><ChevronRight size={16}/><strong>{group}</strong><span className="notice-count">{items.length}</span></summary>
      <ul>{items.map((item, index) => <li key={index} className={`notice-item ${item.priority === 'Empfohlen' ? 'error' : item.group === 'Weitere Hinweise' ? 'info' : 'warning'}`}>
        <div className="notice-subject">{item.subject}</div>
        <div className="notice-detail">{item.detail}<span className="notice-severity">{item.priority === 'Empfohlen' ? 'Fehler · Empfohlen' : item.priority === 'Optional' ? 'Warnung · Optional' : item.group === 'Weitere Hinweise' ? 'Hinweis' : 'Warnung'}</span></div>
      </li>)}</ul>
    </details>)}
  </section>;
}
