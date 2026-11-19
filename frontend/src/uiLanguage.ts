import { useSyncExternalStore } from 'react';
import { english } from './uiMessages';

export type UiLanguage = 'de' | 'en';
type Values = Record<string, string | number | undefined>;
export type Translate = (label: string, values?: Values) => string;

export function preferredLanguage(saved: string | null, languages: readonly string[]): UiLanguage {
  if (saved === 'de' || saved === 'en') return saved;
  for (const tag of languages) {
    const base = tag.split('-')[0].toLowerCase();
    if (base === 'de' || base === 'en') return base;
  }
  return 'de';
}

export function translator(language: UiLanguage): Translate {
  return (label, values) => {
    let template = label;
    if (language === 'en') {
      if (Object.hasOwn(english, label)) template = english[label];
      else {
        // Backend diagnostics may append a filename, IRI or parser error. Preserve that detail.
        const separator = label.indexOf(': ');
        const prefix = label.slice(0, separator);
        if (separator > 0 && Object.hasOwn(english, prefix)) template = english[prefix] + label.slice(separator);
      }
    }
    return values ? template.replace(/\{(\w+)\}/g, (token, name) => String(values[name] ?? token)) : template;
  };
}

const storageKey = 'ontolens-ui-language';
let saved = null;
try { saved = localStorage.getItem(storageKey); } catch { /* Storage is optional. */ }
let current = preferredLanguage(saved, navigator.languages);
const listeners = new Set<() => void>();
const subscribe = (notify: () => void) => { listeners.add(notify); return () => { listeners.delete(notify); }; };
const translations = {de: translator('de'), en: translator('en')};
export function setUiLanguage(next: UiLanguage) {
  current = next;
  document.documentElement.lang = next;
  try { localStorage.setItem(storageKey, next); } catch { /* Still works for this session. */ }
  listeners.forEach(notify => notify());
}
export function useUiLanguage() {
  return useSyncExternalStore(subscribe, () => current);
}
export function useText(): Translate {
  return translations[useUiLanguage()];
}
