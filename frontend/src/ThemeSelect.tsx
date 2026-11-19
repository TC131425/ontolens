export function ThemeSelect({value, onChange, disabled = false}: {value: string; onChange: (value: 'light' | 'dark' | 'both') => void; disabled?: boolean}) {
  return <label className="theme-choice">Farbschema<select value={value} disabled={disabled} onChange={e => onChange(e.target.value as 'light' | 'dark' | 'both')}><option value="light">Hell</option><option value="dark">Dunkel</option><option value="both">Beide</option></select></label>;
}
export function VariantSelect({value, onChange}: {value: string; onChange: (value: string) => void}) {
  return <label className="theme-choice">Vorschau<select value={value} onChange={e => onChange(e.target.value)}><option value="light">Hell</option><option value="dark">Dunkel</option></select></label>;
}
