import { useEffect, useRef, useState } from 'react';
import { ImagePlus, Link2, Table2, X } from 'lucide-react';
import { markdownImage, markdownLink, markdownSlots, markdownTable, usedMarkdownSlots } from './markdownInsert';

export function MarkdownInsertToolbar({draft, disabled, onInsert, getSelectedText}: {draft: string; disabled: boolean; onInsert: (text: string, inline?: boolean) => void; getSelectedText: () => string}) {
  const [form, setForm] = useState<'image' | 'table' | 'link' | null>(null);
  const [path, setPath] = useState('figures/abbildung.png');
  const [alt, setAlt] = useState('Beschreibung der Abbildung');
  const [columns, setColumns] = useState('3');
  const [rows, setRows] = useState('3');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkText, setLinkText] = useState('');
  const [error, setError] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const used = usedMarkdownSlots(draft);
  const complete = markdownSlots.every(slot => used.has(slot.id));
  useEffect(() => {
    if (form) {
      dialog.current?.showModal();
      dialog.current?.querySelector('input')?.focus();
    }
    else dialog.current?.close();
  }, [form]);
  function open(kind: 'image' | 'table' | 'link') {
    setError('');
    if (kind === 'link') {setLinkText(getSelectedText());setLinkUrl('');}
    setForm(kind);
  }
  return <div className="markdown-insert-toolbar" role="group" aria-label="Markdown einfügen">
    <select aria-label="Abschnitt einfügen" value="" disabled={disabled || complete} title={complete ? 'Alle Abschnitte sind bereits eingefügt' : 'Generierten Abschnitt einfügen'} onChange={event => {
      const id = event.target.value;
      if (!used.has(id) && markdownSlots.some(slot => slot.id === id)) onInsert(`<!-- ontolens:${id} -->`);
    }}>
      <option value="" disabled>{complete ? 'Alle Abschnitte vorhanden' : 'Abschnitt einfügen …'}</option>
      {markdownSlots.map(slot => <option value={slot.id} disabled={used.has(slot.id)} key={slot.id}>{slot.label}{used.has(slot.id) ? ' (eingefügt)' : ''}</option>)}
    </select>
    <button className="markdown-insert-icon" type="button" disabled={disabled} title="Link einfügen" aria-label="Link einfügen" onClick={() => open('link')}><Link2 size={19}/></button>
    <button className="markdown-insert-icon" type="button" disabled={disabled} title="Bild einfügen" aria-label="Bild einfügen" onClick={() => open('image')}><ImagePlus size={19}/></button>
    <button className="markdown-insert-icon" type="button" disabled={disabled} title="Tabelle einfügen" aria-label="Tabelle einfügen" onClick={() => open('table')}><Table2 size={19}/></button>
    <dialog className="markdown-insert-dialog" ref={dialog} aria-labelledby="markdown-insert-title" onCancel={() => setForm(null)} onClose={() => setForm(null)}>
      <form onSubmit={event => {
        event.preventDefault();
        if (disabled || !form) return;
        try {
          const block = form === 'image' ? markdownImage(path, alt) : form === 'link' ? markdownLink(linkUrl, linkText) : markdownTable(Number(columns), Number(rows));
          dialog.current?.close();
          setForm(null);
          onInsert(block, form === 'link');
        } catch (failure) {setError(failure instanceof Error ? failure.message : 'Einfügen fehlgeschlagen.');}
      }}>
        <div className="markdown-insert-heading"><h2 id="markdown-insert-title">{form === 'image' ? 'Bild einfügen' : form === 'link' ? 'Link einfügen' : 'Tabelle einfügen'}</h2><button type="button" className="icon" title="Schließen" aria-label="Schließen" onClick={() => setForm(null)}><X size={18}/></button></div>
        {form === 'link' ? <>
          <label>Linkziel<input required inputMode="url" value={linkUrl} onChange={event => setLinkUrl(event.target.value)} placeholder="https://example.org"/></label>
          <label>Linktext<input value={linkText} onChange={event => setLinkText(event.target.value)} placeholder="Bezeichnung"/></label>
        </> : form === 'image' ? <>
          <label>Bildpfad oder URL<input required value={path} onChange={event => setPath(event.target.value)} placeholder="figures/abbildung.png"/></label>
          <label>Alternativtext<input value={alt} onChange={event => setAlt(event.target.value)}/></label>
        </> : <div className="markdown-table-size">
          <label>Spalten<input type="number" min="1" max="10" step="1" required value={columns} onChange={event => setColumns(event.target.value)}/></label>
          <label>Datenzeilen<input type="number" min="1" max="50" step="1" required value={rows} onChange={event => setRows(event.target.value)}/></label>
        </div>}
        {error && <p className="markdown-check-error" role="alert">{error}</p>}
        <div className="markdown-insert-actions"><button type="button" onClick={() => setForm(null)}>Abbrechen</button><button type="submit" className="primary-action" disabled={disabled}>Einfügen</button></div>
      </form>
    </dialog>
  </div>;
}
