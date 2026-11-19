import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/markdownInsert.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022}}).outputText;
const { markdownSlots, usedMarkdownSlots, markdownImage, markdownLink, markdownTable, insertMarkdownBlock, insertMarkdownInline } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

test('all supported sections are offered once and existing aliases disable the canonical slot', () => {
  assert.equal(markdownSlots.length, 9);
  assert.equal(new Set(markdownSlots.map(slot => slot.id)).size, 9);
  const text = '<!-- ontolens:metadata -->\n\n<!-- ONTOLENS:namespace-prefixes -->\n<!-- ontolens:quality -->\n';
  assert.deepEqual([...usedMarkdownSlots(text)], ['metadata', 'prefixes', 'quality-report']);
  assert.deepEqual([...usedMarkdownSlots(text.replace('<!-- ontolens:metadata -->', ''))], ['prefixes', 'quality-report']);
  assert.equal(usedMarkdownSlots('Inline <!-- ontolens:downloads --> example').size, 0);
});

test('insertions preserve surrounding text and get their own block', () => {
  const result = insertMarkdownBlock('Before\n\nAfter', '<!-- ontolens:visualization -->', 8, 8);
  assert.equal(result.text, 'Before\n\n<!-- ontolens:visualization -->\n\nAfter');
  assert.equal(result.text.slice(result.cursor), 'After');
  const replacement = insertMarkdownBlock('Before SELECTED After', 'Block', 7, 15);
  assert.equal(replacement.text, 'Before \n\nBlock\n\n After');
  assert.equal(insertMarkdownBlock('', 'Block').text, 'Block\n');
  assert.equal(insertMarkdownBlock('Before', 'Block').text, 'Before\n\nBlock\n');
  assert.equal(insertMarkdownBlock('Before\n', 'Block').text, 'Before\n\nBlock\n');
});

test('image snippets keep paths with spaces and escape alternative text', () => {
  assert.equal(markdownImage(' figures/my image.svg ', 'A [diagram]'), '![A \\[diagram\\]](<figures/my image.svg>)');
  assert.equal(markdownImage('figures\\diagram.png', ''), '![](<figures/diagram.png>)');
  assert.equal(markdownImage('https://example.org/a(b).svg', 'One\nTwo'), '![One Two](<https://example.org/a(b).svg>)');
  assert.equal(markdownImage('figure>name.png', 'Test'), '![Test](<figure%3Ename.png>)');
  assert.throws(() => markdownImage('  ', 'Missing'));
});

test('table dimensions exclude the header and remain bounded', () => {
  assert.equal(markdownTable(2, 2), '| Spalte 1 | Spalte 2 |\n| --- | --- |\n| Wert | Wert |\n| Wert | Wert |');
  assert.equal(markdownTable(1, 1).split('\n').length, 3);
  assert.equal(markdownTable(10, 50).split('\n').length, 52);
  for (const dimensions of [[0, 3], [11, 3], [2, 0], [2, 51], [1.5, 2], [2, NaN]]) {
    assert.throws(() => markdownTable(...dimensions));
  }
});

test('link snippets support web addresses, mail and fragments with plain link text', () => {
  assert.equal(markdownLink(' https://example.org/a(b)?x=1&y=2 ', 'A [link]'), '[A \\[link\\]](<https://example.org/a(b)?x=1&y=2>)');
  assert.equal(markdownLink('#cross-reference', 'Reference'), '[Reference](<#cross-reference>)');
  assert.equal(markdownLink('mailto:person@example.org', 'Contact'), '[Contact](<mailto:person@example.org>)');
  assert.equal(markdownLink('docs/my page.html', 'Read\nmore'), '[Read more](<docs/my%20page.html>)');
  assert.equal(markdownLink('https://example.org', ''), '[https://example.org](<https://example.org>)');
  assert.equal(markdownLink('https://example.org', '<b>Example</b>'), '[\\<b\\>Example\\</b\\>](<https://example.org>)');
  for (const url of ['', '   ', 'https://', 'javascript:alert(1)', 'data:text/html,test', 'file:///C:/secret', 'java\nscript:alert(1)']) {
    assert.throws(() => markdownLink(url, 'Invalid'));
  }
});

test('inline links replace the selection without breaking a paragraph', () => {
  const result = insertMarkdownInline('Read Example here.', markdownLink('https://example.org', 'Example'), 5, 12);
  assert.equal(result.text, 'Read [Example](<https://example.org>) here.');
  assert.equal(result.text.slice(result.cursor), ' here.');
  assert.equal(insertMarkdownInline('See ', 'link').text, 'See link');
  assert.equal(insertMarkdownInline('', 'link').text, 'link');
});
