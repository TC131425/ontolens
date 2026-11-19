export interface Ontology { id: string; input: string; content: string | null; options: Record<string, string | boolean | null>; html?: Partial<Record<'reference' | 'combined', ExportResult | null>> }
export interface ExportResult { kind: 'reference' | 'combined' | 'markdown'; path: string; preview: string; download: string; notices: string[]; report_available?: boolean; available?: boolean; downloadLabel?: string; variants?: Record<string, {path: string; preview: string}> }
export interface PortalResult extends Omit<ExportResult, 'kind'> { kind: 'portal' }
export interface Project { revision: string; name: string; config: string; output: string; portal: {enabled: boolean; title: string; theme?: 'light' | 'dark' | 'both'; last_title?: string | null; selection?: string[] | null; result?: PortalResult | null}; ontologies: Ontology[]; notices: {ontology: string; message: string}[] }

import { chooseServerFiles } from './FileBrowser';

let projectBase = '';
export function setProjectBase(base: string) {projectBase = base;}
export function apiUrl(path: string) {return projectBase + path;}
let pendingWrites = 0;
export function isProjectBusy() {return pendingWrites > 0;}
export async function apiFetch(path: string, init?: RequestInit) {
  return appFetch(apiUrl(path), init);
}
export async function appFetch(path: string, init?: RequestInit): Promise<Response> {
  const write = !!init?.method && init.method !== 'GET';
  if (write) pendingWrites++;
  try {return await dispatchFetch(path, init);} finally {if (write) pendingWrites--;}
}
async function dispatchFetch(path: string, init?: RequestInit): Promise<Response> {
  const match = path.match(/\/api\/(?:projects\/)?dialog\/(\w+)$/);
  const opening = path === '/api/projects/open';
  if (init?.method === 'POST' && (match || opening)) {
    const runtimeResponse = await fetch('/api/runtime');
    if (!runtimeResponse.ok) throw new Error('Laufzeitkonfiguration konnte nicht geladen werden.');
    const runtime = await runtimeResponse.json();
    if (runtime.file_browser) {
      const kind = opening ? 'project' : match![1];
      const selected = await chooseServerFiles(kind, runtime.root, runtime.host_directory, runtime.host_source);
      if (opening && selected?.length) return fetch(path, {...init, headers: {...init.headers, 'Content-Type': 'application/json'}, body: JSON.stringify({path: selected[0]})});
      const body = opening ? {project: null} : path.includes('/projects/dialog/ontologies') ? {paths: selected || []} : {path: kind === 'ontologies' ? selected : selected?.[0] || null};
      return new Response(JSON.stringify(body), {headers: {'Content-Type': 'application/json'}});
    }
  }
  return fetch(path, init);
}
export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await apiFetch(path, { signal });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : `API-Fehler (${response.status})`);
  }
  return response.json();
}
