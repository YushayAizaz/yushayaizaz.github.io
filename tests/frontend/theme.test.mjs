import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('../../src/scripts/theme.js', import.meta.url), 'utf8');

class FakeElement {
  constructor(button = false) { this.button = button; this.attributes = {}; }
  setAttribute(name, value) { this.attributes[name] = value; }
  closest(selector) { return this.button && selector === '[data-theme-toggle]' ? this : null; }
}
function doc() {
  const classes = new Set();
  const button = new FakeElement(true);
  const meta = new FakeElement();
  const label = { textContent: '' };
  return {
    documentElement: { dataset: {}, style: {}, classList: { add: (s) => classes.add(s), toggle: (s, yes) => yes ? classes.add(s) : classes.delete(s), contains: (s) => classes.has(s) } },
    button, meta, label,
    querySelector: () => meta,
    querySelectorAll: (selector) => selector === '[data-theme-toggle]' ? [button] : [label],
  };
}
function runtime(stored, throws = false) {
  const document = doc();
  const listeners = new Map();
  const store = new Map(stored ? [['yushay-reading-edition', stored]] : []);
  const add = (type, fn) => listeners.set(type, [...(listeners.get(type) ?? []), fn]);
  document.addEventListener = add;
  const window = { addEventListener: add };
  const context = vm.createContext({ document, window, Element: FakeElement, localStorage: {
    getItem(key) { if (throws) throw Error('blocked'); return store.get(key); },
    setItem(key, value) { if (throws) throw Error('blocked'); store.set(key, value); },
  } });
  vm.runInContext(source, context);
  const dispatch = (type, event = {}) => { for (const fn of listeners.get(type) ?? []) fn(event); };
  return { document, listeners, store, context, dispatch };
}

test('first visit defaults to Warm Literary Press', () => {
  const { document } = runtime();
  assert.equal(document.documentElement.dataset.theme, 'light');
  assert.equal(document.button.attributes['aria-pressed'], 'false');
  assert.equal(document.label.textContent, 'Warm Literary Press');
});
test('saved Nocturne is applied before painting and the toggle persists changes', () => {
  const app = runtime('dark');
  assert.equal(app.document.documentElement.classList.contains('dark'), true);
  assert.equal(app.document.meta.attributes.content, '#0E0F12');
  app.dispatch('click', { target: app.document.button });
  assert.equal(app.store.get('yushay-reading-edition'), 'light');
  assert.equal(app.document.button.attributes['aria-pressed'], 'false');
});
test('disabled storage still allows a session theme and transition persistence', () => {
  const app = runtime(undefined, true);
  app.dispatch('click', { target: app.document.button });
  const newDocument = doc();
  app.dispatch('astro:before-swap', { newDocument });
  assert.equal(newDocument.documentElement.dataset.theme, 'dark');
  assert.equal(newDocument.button.attributes['aria-pressed'], 'true');
});
test('cross-tab changes and cleared storage synchronize the edition', () => {
  const app = runtime();
  app.dispatch('storage', { key: 'yushay-reading-edition', newValue: 'dark' });
  assert.equal(app.document.label.textContent, 'Nocturne Edition');
  app.dispatch('storage', { key: null, newValue: null });
  assert.equal(app.document.label.textContent, 'Warm Literary Press');
});
test('rerunning the head script does not attach duplicate listeners', () => {
  const app = runtime();
  vm.runInContext(source, app.context);
  assert.equal(app.listeners.get('click').length, 1);
  app.dispatch('click', { target: app.document.button });
  assert.equal(app.document.documentElement.dataset.theme, 'dark');
});
