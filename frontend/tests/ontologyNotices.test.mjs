import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/ontologyNotices.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022}}).outputText;
const { ontologyNotices } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const ontology = {id: 'cero', input: 'cero.ttl', content: null, options: {}};
const output = (notices, report_available = true) => ({kind: 'reference', path: 'cero.html', notices, report_available});

test('unbuilt or manually assigned documents do not imply a clean quality check', () => {
  assert.equal(ontologyNotices(ontology, []).generated, false);
  assert.equal(ontologyNotices({...ontology, html: {reference: output([], false)}}, []).generated, false);
  assert.equal(ontologyNotices({...ontology, html: {reference: output([])}}, []).generated, true);
});

test('all 83 saved generation notices reach the shared report', () => {
  const notices = [...Array.from({length: 13}, (_, i) => `Missing optional metadata: field ${i}`),
    ...Array.from({length: 70}, (_, i) => `cero:Class${i} has no comment`)];
  const saved = {...ontology, html: {reference: output(notices)}};
  assert.deepEqual(ontologyNotices(saved, []).notices, notices);
  assert.equal(ontologyNotices(saved, []).generated, true);
  assert.deepEqual(ontologyNotices(JSON.parse(JSON.stringify(saved)), []).notices, notices);
});

test('project and HTML variants are combined without double counting', () => {
  const reference = output(['cero:Class has no comment', 'Abbildung übersprungen: figures/model.svg']);
  const combined = output(['cero:Class has no comment', 'Introduction: empty']);
  const report = ontologyNotices({...ontology, html: {reference, combined}}, [
    {ontology: 'cero', message: 'Abbildung fehlt: figures/model.svg'},
    {ontology: 'another', message: 'Unrelated'},
  ]);
  assert.deepEqual(report.notices, ['Abbildung fehlt: figures/model.svg', 'cero:Class has no comment', 'Introduction: empty']);
  assert.match(report.context, /HTML-Dokumentation \+ Kombinierte Dokumentation/);
});

test('detaching or replacing a document removes its previous notices', () => {
  const linked = {...ontology, html: {reference: output(['Old']), combined: output(['Current'])}};
  assert.deepEqual(ontologyNotices(linked, []).notices, ['Old', 'Current']);
  assert.deepEqual(ontologyNotices({...linked, html: {...linked.html, reference: null}}, []).notices, ['Current']);
  assert.deepEqual(ontologyNotices({...linked, html: {reference: output([], false)}}, []).notices, []);
});

test('legacy notices and missing output files still retain known results', () => {
  const legacy = {notices: ['Saved warning'], available: false};
  assert.equal(ontologyNotices({...ontology, html: {reference: legacy}}, []).generated, true);
  assert.deepEqual(ontologyNotices({...ontology, html: {reference: legacy}}, []).notices, ['Saved warning']);
});
