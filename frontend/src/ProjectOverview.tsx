import type { Project } from './api';
import { ontologyNotices } from './ontologyNotices';

export function ProjectOverview({ project }: { project: Project }) {
  const documents = new Set(project.ontologies.map(o => o.content).filter(Boolean)).size;
  const notices = project.ontologies.flatMap(ontology => ontologyNotices(ontology, project.notices ?? []).notices.map(message => ({ontology: ontology.id, message})));
  return <section aria-label="Projektübersicht" className="project-overview">
    <div className="overview-counts">
      <div><strong>{project.ontologies.length}</strong><span>Ontologien</span></div>
      <div><strong>{documents}</strong><span>{documents === 1 ? 'Markdown-Dokument' : 'Markdown-Dokumente'}</span></div>
      <div className={notices.length ? 'overview-warning' : ''}><strong>{notices.length}</strong><span>{notices.length === 1 ? 'Bekannter Hinweis' : 'Bekannte Hinweise'}</span></div>
    </div>
    {notices.length > 0 && <details className="overview-notices"><summary>Hinweise ansehen</summary><ul>{notices.map((notice, i) => <li key={`${notice.ontology}-${i}`}><strong>{notice.ontology}</strong>: {notice.message}</li>)}</ul></details>}
  </section>;
}
