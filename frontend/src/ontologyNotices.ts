import type { Ontology, Project } from './api';

export function ontologyNotices(ontology: Ontology, projectNotices: Project['notices'], t = (label: string) => label) {
  const messages = new Map<string, string>();
  const add = (message: string) => {
    // The file check and generator describe the same missing figure differently.
    const key = message.replace(/^Abbildung (fehlt|übersprungen): /, 'Abbildung: ');
    if (!messages.has(key)) messages.set(key, message);
  };
  projectNotices.filter(notice => notice.ontology === ontology.id).forEach(notice => add(notice.message));
  const sources: string[] = [];
  for (const kind of ['reference', 'combined'] as const) {
    const result = ontology.html?.[kind];
    if (!result || !(result.report_available ?? (result.notices.length > 0))) continue;
    sources.push(t(kind === 'reference' ? 'HTML-Dokumentation' : 'Kombinierte Dokumentation'));
    result.notices.forEach(add);
  }
  const generated = sources.length > 0;
  return {
    notices: [...messages.values()], generated,
    context: generated
      ? t('Projektdateien und gespeicherte Prüfhinweise: {sources}. Stand der verknüpften Ausgaben, keine erneute Inhaltsprüfung.').replace('{sources}', () => sources.join(' + '))
      : t('Projektdateien geprüft · Noch kein gespeicherter Prüfbericht einer HTML-Generierung.'),
    emptyMessage: t(generated ? 'Keine Hinweise aus der Projektprüfung und den gespeicherten Generierungsprüfungen.' : 'Noch kein gespeicherter Prüfbericht. Bei den Projektdateien wurden keine Probleme gefunden.'),
  };
}
