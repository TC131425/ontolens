import Markdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useEffect, useRef, useState } from 'react';
import { Download, Save, ListChecks, BookOpen, Pencil, FileText, ImageOff } from 'lucide-react';
import { apiFetch, apiUrl } from './api';
import type { ExportResult } from './api';
import { VariantSelect } from './ThemeSelect';
import { MarkdownInsertToolbar } from './MarkdownInsertToolbar';
import { insertMarkdownBlock, insertMarkdownInline } from './markdownInsert';

interface ImagePreview { src: string; alt: string; preview: string | null; error: string }

function sameImageSource(left: string, right?: string) {
  if (!right) return false;
  try {return decodeURI(left) === decodeURI(right);} catch {return left === right;}
}

function MarkdownImage({ image, alt, title }: { image?: ImagePreview; alt?: string; title?: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [image?.preview]);
  const problem = image?.error || (failed ? 'Bild konnte nicht geladen werden.' : '');
  if (problem) return <span className="markdown-image-error" role="alert"><ImageOff size={18}/><span><strong>{alt || image?.src || 'Abbildung'}</strong><span>{problem}</span></span></span>;
  if (!image?.preview) return <span className="image-placeholder">Abbildung wird geprüft …</span>;
  return <img className="markdown-image" src={image.preview} alt={alt || ''} title={title} referrerPolicy="no-referrer" onError={() => setFailed(true)}/>;
}

export function ExportPreview({ mode, result: linked, markdown, loading, error, ontologyId, projectRevision, contentRevision, contentPath, onSaved, onDirty }: {mode: ExportResult['kind']; result?: ExportResult; markdown: string | null; loading: boolean; error: string; ontologyId: string; projectRevision: string; contentRevision: string; contentPath: string | null; onSaved: (content: string, revision: string) => void; onDirty: (dirty: boolean) => void}) {
  const [variant, setVariant] = useState('light');
  const result = linked ? {...linked, ...linked.variants?.[variant]} : linked;
  const [source, setSource] = useState(false);
  const [draft, setDraft] = useState(markdown ?? '');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState('');
  const [checked, setChecked] = useState<{text: string; issues: {chapter: string; title: string; kind: string}[]} | null>(null);
  const [imageState, setImageState] = useState<{text: string; path: string; images: ImagePreview[]} | null>(null);
  const [imageError, setImageError] = useState('');
  const saveButton = useRef<HTMLButtonElement>(null);
  const editor = useRef<HTMLTextAreaElement>(null);
  const selection = useRef<{start: number; end: number} | null>(null);
  const images = imageState?.text === draft && imageState.path === contentPath ? imageState.images : [];
  const imageIssues = images.filter(image => image.error);
  const dirty = markdown !== null && draft !== markdown;
  const documentPath = mode === 'markdown' ? contentPath : result?.path;
  useEffect(() => {setDraft(markdown ?? '');setMessage('');}, [markdown, contentPath]);
  useEffect(() => {setChecked(null);setCheckError('');selection.current = null;}, [contentPath]);
  useEffect(() => {onDirty(dirty);}, [dirty, onDirty]);
  useEffect(() => {
    if (mode !== 'markdown' || markdown === null || !contentPath || loading || error) return;
    const controller = new AbortController();
    setImageError('');
    const timer = window.setTimeout(async () => {
      try {
        const response = await apiFetch(`/api/ontologies/${encodeURIComponent(ontologyId)}/markdown/images`, {
          method: 'POST', signal: controller.signal, headers: {'Content-Type': 'application/json', 'X-Ontolens-Write': '1'},
          body: JSON.stringify({revision: projectRevision, content: draft}),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Bildprüfung fehlgeschlagen');
        if (!controller.signal.aborted) setImageState({text: draft, path: contentPath, images: result.images});
      } catch (failure) {
        if (!controller.signal.aborted) setImageError(failure instanceof Error ? failure.message : 'Bildprüfung fehlgeschlagen');
      }
    }, 450);
    return () => {window.clearTimeout(timer);controller.abort();};
  }, [draft, contentPath, ontologyId, projectRevision, mode, markdown, loading, error]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {if (dirty) {event.preventDefault();event.returnValue = '';}};
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  async function save() {
    setSaving(true);setMessage('');
    try {
      const response = await apiFetch(`/api/ontologies/${encodeURIComponent(ontologyId)}/markdown`, {method: 'PUT', headers: {'Content-Type': 'application/json', 'X-Ontolens-Write': '1'}, body: JSON.stringify({revision: projectRevision, content_revision: contentRevision, content: draft})});
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Speichern fehlgeschlagen');
      onSaved(result.content, result.content_revision);
      setMessage('Arbeitsdatei gespeichert.');
    } catch (error) {setMessage(error instanceof Error ? error.message : 'Speichern fehlgeschlagen');}
    finally {setSaving(false);}
  }
  async function check() {
    const text = draft;
    setChecking(true);setCheckError('');
    try {
      const response = await apiFetch(`/api/ontologies/${encodeURIComponent(ontologyId)}/markdown/check`, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Ontolens-Write': '1'}, body: JSON.stringify({revision: projectRevision, content: text})});
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Prüfung fehlgeschlagen');
      setChecked({text, issues: result.issues});
      if (contentPath) setImageState({text, path: contentPath, images: result.images});
      setImageError('');
    } catch (error) {setCheckError(error instanceof Error ? error.message : 'Prüfung fehlgeschlagen');}
    finally {setChecking(false);}
  }
  function getSelectedText() {
    return editor.current?.value.slice(selection.current?.start ?? 0, selection.current?.end ?? 0) ?? '';
  }
  function insert(block: string, inline = false) {
    if (!editor.current || saving || loading || markdown === null || error) return;
    const text = editor.current.value;
    const insertion = (inline ? insertMarkdownInline : insertMarkdownBlock)(text, block, selection.current?.start ?? text.length, selection.current?.end ?? text.length);
    editor.current.focus();
    editor.current.setSelectionRange(insertion.start, insertion.end);
    // Native insertion preserves the textarea's undo history where supported.
    try {document.execCommand('insertText', false, insertion.replacement);} catch { /* Controlled value below is the fallback. */ }
    setDraft(insertion.text);
    setMessage('');
    selection.current = {start: insertion.cursor, end: insertion.cursor};
    requestAnimationFrame(() => {
      editor.current?.focus();
      editor.current?.setSelectionRange(insertion.cursor, insertion.cursor);
    });
  }
  return <section className={`document${mode === 'markdown' ? ' markdown-document' : ''}`} onKeyDown={event => {
    if (mode === 'markdown' && contentPath && (event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 's') {
      event.preventDefault();
      if (!event.repeat && !(event.target instanceof Element && event.target.closest('dialog'))) saveButton.current?.click();
    }
  }}>
    <div className="document-header"><strong>{mode === 'reference' ? 'HTML-Dokumentation' : mode === 'combined' ? 'Kombinierte Dokumentation' : 'Markdown'}</strong>
      {mode === 'markdown' && contentPath ? <a className="export-download" title="Gespeichertes Markdown herunterladen" href={apiUrl(`/api/ontologies/${encodeURIComponent(ontologyId)}/markdown/download`)}><Download size={16}/>Herunterladen</a> : result && result.available !== false && <a className="export-download" href={result.download}>{result.downloadLabel || 'ZIP herunterladen'}</a>}
      {documentPath && <details className="document-location"><summary><FileText size={15}/><span>{documentPath.split(/[\\/]/).pop()}</span></summary><div>{documentPath}</div></details>}
      {mode !== 'markdown' && result?.variants?.dark && <VariantSelect value={variant} onChange={setVariant}/>}
    </div>
    {mode !== 'markdown' ? result ? result.available === false ? <div className="empty" role="alert"><h2>HTML-Datei nicht gefunden</h2><p>Bitte die Datei neu zuordnen oder die Verknüpfung lösen.</p></div> : <><p className="markdown-message">Verknüpfte Ausgabe · Wird bei Änderungen an Quellen und Optionen nicht automatisch aktualisiert.</p><iframe className="html-export-preview" title="Erzeugte HTML-Dokumentation" src={result.preview} sandbox="allow-scripts allow-downloads"/></> : <div className="empty"><h2>Keine HTML-Datei zugeordnet</h2><p>Dokumentation generieren oder eine vorhandene HTML-Datei auswählen.</p></div> : <>
      <div className="markdown-toolbar">
        <div className="view-switch" role="group" aria-label="Markdown-Ansicht">
          <button aria-pressed={!source} onClick={() => setSource(false)}><BookOpen size={16}/>Lesen</button>
          <button aria-pressed={source} onClick={() => setSource(true)}><Pencil size={16}/>Bearbeiten</button>
        </div>
        <button disabled={checking || loading || markdown === null || !!error} onClick={check}><ListChecks size={17}/>{checking ? 'Prüft …' : 'Prüfen'}</button>
        <button ref={saveButton} className="markdown-save" title="Markdown speichern (Strg+S)" aria-keyshortcuts="Control+s Meta+s" disabled={!dirty || saving || loading || !!error} onClick={save}><Save size={17}/>{saving ? 'Speichert …' : 'Speichern'}</button>
        <span className="markdown-save-state" role="status">{dirty ? 'Ungespeicherte Änderungen' : contentPath && !loading ? 'Gespeichert' : ''}</span>
      </div>
      {source && <MarkdownInsertToolbar draft={draft} disabled={saving || loading || markdown === null || !!error} onInsert={insert} getSelectedText={getSelectedText}/>}
      <div className="paper">{loading ? 'Markdown wird geladen …' : error ? <p role="alert">{error}</p> : markdown === null ? <p>Bitte eine Vorlage erzeugen oder Markdown zuordnen.</p> : source ? <textarea ref={editor} className="markdown-editor" aria-label="Markdown bearbeiten" readOnly={saving} value={draft} onSelect={event => {selection.current = {start: event.currentTarget.selectionStart, end: event.currentTarget.selectionEnd};}} onChange={event => setDraft(event.target.value)}/> : <Markdown remarkPlugins={[remarkGfm]} urlTransform={(url, key) => key === 'src' ? url : defaultUrlTransform(url)} components={{img: ({src, alt, title}) => <MarkdownImage image={images.find(image => sameImageSource(image.src, src))} alt={alt} title={title}/>}}>{draft.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '')}</Markdown>}</div>
      <div className="markdown-feedback">
      {(imageError || imageIssues.length > 0) && <div className="markdown-image-notices" aria-live="polite">
        <strong>Bilder prüfen{imageIssues.length > 0 ? ` (${imageIssues.length})` : ''}</strong>
        {imageError && <p>{imageError}</p>}
        {imageIssues.length > 0 && <ul>{imageIssues.map(image => <li key={image.src}><code>{image.src}</code><span>{image.error}</span></li>)}</ul>}
      </div>}
      {checkError && <p className="markdown-check-error" role="alert">{checkError}</p>}
      {checked && <details className="markdown-check-results" open key={checked.text}>
        <summary>{checked.text !== draft ? 'Prüfergebnis veraltet · ' : ''}{checked.issues.length ? `${checked.issues.length} Kapitelhinweise` : 'Kapitelprüfung ohne Hinweise'}</summary>
        <p>Strukturelle Vollständigkeit{checked.text !== draft ? ' · Bitte erneut prüfen.' : ''}</p>
        {checked.issues.length > 0 && <ul>{checked.issues.map(issue => <li key={issue.chapter}><strong>{issue.title}</strong><span>{issue.kind === 'missing' ? 'Kapitel fehlt' : 'Kapitel enthält noch keinen Inhalt'}</span></li>)}</ul>}
      </details>}
      {message && <p className="markdown-message" role="status">{message}</p>}
      </div>
    </>}
  </section>;
}
