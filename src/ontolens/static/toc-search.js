(() => {
  const toc = document.querySelector('aside.toc');
  const tools = toc?.querySelector('.toc-search');
  if (!tools) return;
  const list = toc.querySelector('#toc-list');
  const input = tools.querySelector('input[type="search"]');
  const clear = tools.querySelector('button');
  const status = tools.querySelector('[role="status"]');
  const scopes = [...tools.querySelectorAll('.toc-scopes input')];
  const scopeCount = tools.querySelector('.toc-scopes summary span');
  const german = document.documentElement.lang.toLowerCase().split('-')[0] === 'de';
  const sources = {Comments: 'Kommentar', Description: 'Beschreibung', Abstract: 'Kurzfassung',
    Definition: 'Definition', 'Scope note': 'Anwendungshinweis', 'History note': 'Änderungshinweis',
    Example: 'Beispiel', 'Chapter text': 'Kapiteltext'};
  const normalize = text => text.replace(/\s+/gu, ' ').trim();
  const details = [...list.querySelectorAll('details')];
  let entries, savedState, lastHeading, highlightTimer;

  // Index the finished navigation: combined pages rebuild it around the Markdown chapters.
  function index() {
    const chapters = new Map();
    for (const block of document.querySelectorAll('main > [data-toc-chapter]')) {
      const id = block.dataset.tocChapter;
      if (!id || block.matches('h1,h2,h3')) continue;
      const text = normalize(block.innerText ?? block.textContent);
      if (!text) continue;
      if (!chapters.has(id)) chapters.set(id, []);
      chapters.get(id).push({scope: 'markdown', text, source: 'Chapter text'});
    }
    return [...list.querySelectorAll('li')].map(item => {
      const link = item.querySelector(':scope > a');
      const group = item.querySelector(':scope > details');
      const caption = link || group.querySelector('summary > span');
      const target = link && document.getElementById(link.getAttribute('href').slice(1));
      const title = caption.textContent;
      let titleScope = target?.hasAttribute('data-toc-chapter') ? 'markdown' : 'names';
      const fields = [];
      if (target?.matches('article.term, #metadata')) {
        for (const label of target.querySelectorAll('.term-label')) {
          fields.push({scope: 'names', text: normalize(label.textContent), lang: label.lang});
        }
        if (target.matches('article.term')) {
          const curie = target.querySelector('.term-curie').textContent;
          const iri = target.querySelector('.term-iri').getAttribute('href');
          if ((title === curie || title === iri) && !fields.some(f => f.text === title)) titleScope = 'iris';
          fields.push({scope: 'iris', text: curie}, {scope: 'iris', text: iri});
        }
        for (const field of target.querySelectorAll('[data-toc-text]')) {
          fields.push({scope: 'prose', text: normalize(field.textContent), lang: field.lang, source: field.dataset.tocText});
        }
      }
      if (chapters.has(target?.id)) fields.push(...chapters.get(target.id));
      return {item, caption, title, titleScope, fields, group,
        category: !!group || (item.matches('.toc-group:not(.toc-reference)') && !!item.querySelector(':scope > ul')),
        badge: group?.querySelector('.toc-count'), decorated: false};
    });
  }

  function mark(element, text, pattern) {
    let end = 0;
    element.replaceChildren();
    for (const match of text.matchAll(pattern)) {
      const hit = document.createElement('mark');
      hit.textContent = match[0];
      element.append(text.slice(end, match.index), hit);
      end = match.index + match[0].length;
    }
    element.append(text.slice(end));
  }

  function excerpt(text, match) {
    const start = Math.max(0, match.index - 48);
    const end = Math.min(text.length, match.index + match[0].length + 80);
    const before = text.slice(start, match.index);
    const after = text.slice(match.index + match[0].length, end);
    return (start ? '…' + before.replace(/^\S*\s/u, ' ') : before) + match[0]
      + (end < text.length ? after.replace(/\s\S*$/u, ' ') + '…' : after);
  }

  function filter() {
    const query = input.value.trim();
    const enabled = new Set(scopes.filter(box => box.checked).map(box => box.value));
    scopeCount.textContent = enabled.size === scopes.length ? '' : '(' + enabled.size + '/' + scopes.length + ')';
    clear.hidden = !input.value;
    if (!query && !savedState) return;
    entries ??= index();
    if (!savedState) savedState = details.map(group => group.open);
    toc.classList.toggle('is-filtered', !!query);
    const literal = query.replace(/[.*+?^$\{}()|[\]\\]/g, '\\$&');
    const pattern = new RegExp(literal, 'iu');
    const highlights = new RegExp(literal, 'giu');
    const visible = new Set();
    const matchedCategories = new Set();
    let count = 0;
    for (const entry of entries) {
      const {item, title, fields, caption} = entry;
      if (entry.decorated) {
        caption.textContent = title;
        entry.decorated = false;
      }
      if (!query) { item.hidden = false; continue; }
      const inTitle = enabled.has(entry.titleScope) && pattern.test(title);
      const field = !inTitle && fields.find(value => enabled.has(value.scope) && pattern.test(value.text));
      const parent = item.parentElement.closest('li');
      if (!inTitle && !field && !matchedCategories.has(parent)) continue;
      if (inTitle) {
        mark(caption, title, highlights);
        if (entry.category) matchedCategories.add(item);
        entry.decorated = true;
      } else if (field) {
        const hint = document.createElement('small');
        hint.className = 'toc-match-field';
        mark(hint, field.source ? excerpt(field.text, pattern.exec(field.text)) : field.text, highlights);
        if (field.lang) hint.lang = field.lang;
        if (field.source) {
          const source = document.createElement('span');
          source.className = 'toc-match-source';
          source.lang = document.documentElement.lang;
          source.textContent = (german ? sources[field.source] : field.source) + (field.lang ? ' · ' + field.lang : '');
          hint.prepend(source);
        } else if (field.lang) hint.append(' [' + field.lang + ']');
        caption.append(hint);
        entry.decorated = true;
      }
      if (!entry.category) count++;
      for (let ancestor = item; ancestor && !visible.has(ancestor); ancestor = ancestor.parentElement.closest('li')) {
        visible.add(ancestor);
      }
    }
    if (query) {
      for (const {item, group} of entries) {
        item.hidden = !visible.has(item);
        if (group) group.open = !item.hidden;
      }
      status.textContent = !enabled.size ? status.dataset.empty
        : count ? count + ' ' + (count === 1 ? status.dataset.one : status.dataset.many) : status.dataset.none;
    } else {
      details.forEach((group, i) => { group.open = savedState[i]; });
      savedState = null;
      status.textContent = '';
    }
    for (const {group, badge} of entries) {
      if (badge) badge.textContent = group.querySelectorAll(':scope > ul > li:not([hidden])').length;
    }
  }

  function reset() { input.value = ''; filter(); input.focus(); }
  input.addEventListener('input', filter);
  scopes.forEach(box => box.addEventListener('change', filter));
  clear.addEventListener('click', reset);
  tools.addEventListener('keydown', event => {
    if (event.key === 'Escape' && input.value) { event.preventDefault(); reset(); }
  });
  list.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (!savedState || !link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const target = document.getElementById(link.getAttribute('href').slice(1));
    const heading = target?.matches('h1,h2,h3') ? target : target?.querySelector('h1,h2,h3');
    if (!heading) return;
    clearTimeout(highlightTimer);
    lastHeading?.classList.remove('toc-jump-highlight');
    heading.classList.add('toc-jump-highlight');
    lastHeading = heading;
    highlightTimer = setTimeout(() => heading.classList.remove('toc-jump-highlight'), 1500);
  });
  tools.hidden = false;
})();
