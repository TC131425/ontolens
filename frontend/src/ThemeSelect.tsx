import { useText } from './uiLanguage';
export function ThemeSelect({value, onChange, disabled = false}: {value: string; onChange: (value: 'light' | 'dark' | 'both') => void; disabled?: boolean}) {
  const t = useText();
  return <label className="theme-choice">{t("Farbschema")}<select value={value} disabled={disabled} onChange={e => onChange(e.target.value as 'light' | 'dark' | 'both')}><option value="light">{t("Hell")}</option><option value="dark">{t("Dunkel")}</option><option value="both">{t("Beide")}</option></select></label>;
}
export function VariantSelect({value, onChange}: {value: string; onChange: (value: string) => void}) {
  const t = useText();
  return <label className="theme-choice">{t("Vorschau")}<select value={value} onChange={e => onChange(e.target.value)}><option value="light">{t("Hell")}</option><option value="dark">{t("Dunkel")}</option></select></label>;
}
