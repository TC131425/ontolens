import { useText } from './uiLanguage';
import { useEffect, useRef, useState } from 'react';
import { ImagePlus, Link2, Table2, X } from 'lucide-react';
import { markdownImage, markdownLink, markdownSlots, markdownTable, usedMarkdownSlots } from './markdownInsert';

export function MarkdownInsertToolbar({draft, disabled, onInsert, getSelectedText}: {draft: string; disabled: boolean; onInsert: (text: string, inline?: boolean) => void; getSelectedText: () => string}) {
  const t = useText();
  const [form, setForm] = useState<'image' | 'table' | 'link' | null>(null);
  const [path, setPath] = useState(t("figures/abbildung.png"));
  const [alt, setAlt] = useState(t("Beschreibung der Abbildung"));
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
  return <div className="markdown-insert-toolbar" role="group" aria-label={t("Markdown einfügen")}>
    <select aria-label={t("Abschnitt einfügen")} value="" disabled={disabled || complete} title={complete ? t("Alle Abschnitte sind bereits eingefügt") : t("Generierten Abschnitt einfügen")} onChange={event => {
      const id = event.target.value;
      if (!used.has(id) && markdownSlots.some(slot => slot.id === id)) onInsert(`<!-- ontolens:${id} -->`);
    }}>
      <option value="" disabled>{complete ? t("Alle Abschnitte vorhanden") : t("Abschnitt einfügen …")}</option>
      {markdownSlots.map(slot => <option value={slot.id} disabled={used.has(slot.id)} key={slot.id}>{t(slot.label)}{used.has(slot.id) ? " " + t("(eingefügt)") : ''}</option>)}
    </select>
    <button className="markdown-insert-icon" type="button" disabled={disabled} title={t("Link einfügen")} aria-label={t("Link einfügen")} onClick={() => open('link')}><Link2 size={19}/></button>
    <button className="markdown-insert-icon" type="button" disabled={disabled} title={t("Bild einfügen")} aria-label={t("Bild einfügen")} onClick={() => open('image')}><ImagePlus size={19}/></button>
    <button className="markdown-insert-icon" type="button" disabled={disabled} title={t("Tabelle einfügen")} aria-label={t("Tabelle einfügen")} onClick={() => open('table')}><Table2 size={19}/></button>
    <dialog className="markdown-insert-dialog" ref={dialog} aria-labelledby="markdown-insert-title" onCancel={() => setForm(null)} onClose={() => setForm(null)}>
      <form onSubmit={event => {
        event.preventDefault();
        if (disabled || !form) return;
        try {
          const block = form === 'image' ? markdownImage(path, alt) : form === 'link' ? markdownLink(linkUrl, linkText) : markdownTable(Number(columns), Number(rows), t);
          dialog.current?.close();
          setForm(null);
          onInsert(block, form === 'link');
        } catch (failure) {setError(failure instanceof Error ? failure.message : 'Einfügen fehlgeschlagen.');}
      }}>
        <div className="markdown-insert-heading"><h2 id="markdown-insert-title">{form === 'image' ? t("Bild einfügen") : form === 'link' ? t("Link einfügen") : t("Tabelle einfügen")}</h2><button type="button" className="icon" title={t("Schließen")} aria-label={t("Schließen")} onClick={() => setForm(null)}><X size={18}/></button></div>
        {form === 'link' ? <>
          <label>{t("Linkziel")}<input required inputMode="url" value={linkUrl} onChange={event => setLinkUrl(event.target.value)} placeholder="https://example.org"/></label>
          <label>{t("Linktext")}<input value={linkText} onChange={event => setLinkText(event.target.value)} placeholder={t("Bezeichnung")}/></label>
        </> : form === 'image' ? <>
          <label>{t("Bildpfad oder URL")}<input required value={path} onChange={event => setPath(event.target.value)} placeholder={t("figures/abbildung.png")}/></label>
          <label>{t("Alternativtext")}<input value={alt} onChange={event => setAlt(event.target.value)}/></label>
        </> : <div className="markdown-table-size">
          <label>{t("Spalten")}<input type="number" min="1" max="10" step="1" required value={columns} onChange={event => setColumns(event.target.value)}/></label>
          <label>{t("Datenzeilen")}<input type="number" min="1" max="50" step="1" required value={rows} onChange={event => setRows(event.target.value)}/></label>
        </div>}
        {error && <p className="markdown-check-error" role="alert">{t(error)}</p>}
        <div className="markdown-insert-actions"><button type="button" onClick={() => setForm(null)}>{t("Abbrechen")}</button><button type="submit" className="primary-action" disabled={disabled}>{t("Einfügen")}</button></div>
      </form>
    </dialog>
  </div>;
}
