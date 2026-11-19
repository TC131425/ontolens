import { useText } from './uiLanguage';
import type { Project } from './api';
import { ontologyNotices } from './ontologyNotices';
import { formatNotice } from './ExportNotices';

export function ProjectOverview({ project }: { project: Project }) {
  const t = useText();
  const documents = new Set(project.ontologies.map(o => o.content).filter(Boolean)).size;
  const notices = project.ontologies.flatMap(ontology => ontologyNotices(ontology, project.notices ?? []).notices.map(message => ({ontology: ontology.id, message})));
  return <section aria-label={t("Projektübersicht")} className="project-overview">
    <div className="overview-counts">
      <div><strong>{project.ontologies.length}</strong><span>{t(project.ontologies.length === 1 ? "Ontologie" : "Ontologien")}</span></div>
      <div><strong>{documents}</strong><span>{documents === 1 ? t("Markdown-Dokument") : t("Markdown-Dokumente")}</span></div>
      <div className={notices.length ? 'overview-warning' : ''}><strong>{notices.length}</strong><span>{notices.length === 1 ? t("Bekannter Hinweis") : t("Bekannte Hinweise")}</span></div>
    </div>
    {notices.length > 0 && <details className="overview-notices"><summary>{t("Hinweise ansehen")}</summary><ul>{notices.map((notice, i) => {
      const {subject, detail} = formatNotice(notice.message, t);
      return <li key={`${notice.ontology}-${i}`}><strong>{notice.ontology}</strong>: {subject}{detail && ': ' + t(detail)}</li>;
    })}</ul></details>}
  </section>;
}
