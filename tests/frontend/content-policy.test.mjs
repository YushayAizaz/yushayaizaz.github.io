import test from 'node:test';
import assert from 'node:assert/strict';
import { allowDraftPreview, visibleEntries, newestFirst, featuredEntry, mediaLabel, selectEvent, eventLabel, plainExcerpt } from '../../src/lib/content-policy.ts';

const entry = (id, draft, date, extra = {}) => ({ id, data: { draft, date: new Date(date), ...extra } });

test('drafts require the dev command, dev mode and an exact true flag', () => {
  assert.equal(allowDraftPreview(true, true, 'true'), true);
  for (const args of [[false, true, 'true'], [true, false, 'true'], [false, false, 'true'], [true, true, 'false'], [true, true, undefined], [true, true, true], [true, true, 'TRUE']]) {
    assert.equal(allowDraftPreview(...args), false);
  }
});
test('the default visibility filter excludes drafts and never mutates input', () => {
  const all = [entry('draft', true, '2026-01-01'), entry('published', false, '2026-01-02')];
  assert.deepEqual(visibleEntries(all).map(x => x.id), ['published']);
  assert.equal(visibleEntries(all, true).length, 2);
  assert.equal(all.length, 2);
  assert.deepEqual(visibleEntries([]), []);
});
test('featured selection honors the flag and falls back deterministically', () => {
  const old = entry('old', false, '2026-01-01', { featured: true });
  const newer = entry('newer', false, '2026-02-01', { featured: false });
  assert.equal(featuredEntry([newer, old]).id, 'old');
  assert.equal(featuredEntry([newer, { ...old, data: { ...old.data, featured: false } }]).id, 'newer');
  assert.equal(featuredEntry([]), undefined);
  assert.equal(newestFirst([entry('b', false, '2026-01-01'), entry('a', false, '2026-01-01')])[0].id, 'a');
});
test('zero, single and carousel media use honest labels', () => {
  assert.equal(mediaLabel([]), 'FROM THE NOTEBOOK');
  assert.equal(mediaLabel(['one']), 'PHOTOGRAPH · 1 PLATE');
  assert.equal(mediaLabel(['one', 'two', 'three']), 'CAROUSEL · 3 PLATES');
});
test('ledger prefers nearest upcoming event, then latest past milestone', () => {
  const now = new Date('2026-11-15T12:00:00Z');
  const past = entry('past', false, '2026-11-14', { type: 'milestone' });
  const upcoming = entry('near', false, '2026-11-16', { type: 'upcoming-event' });
  const later = entry('later', false, '2026-11-20', { type: 'upcoming-event' });
  assert.equal(selectEvent([later, past, upcoming], now).id, 'near');
  assert.equal(selectEvent([past], now).id, 'past');
  assert.equal(selectEvent([], now), undefined);
  assert.equal(selectEvent([entry('future-award', false, '2099-01-01', { type: 'award' })], now), undefined);
  assert.equal(eventLabel('upcoming-event', new Date('2026-11-14'), now), 'From the events ledger');
});
test('plain excerpts remove markup and handle long words without empty output', () => {
  assert.equal(plainExcerpt('## Heading\n\n**A thought** and [a link](https://example.com).'), 'Heading A thought and a link.');
  assert.equal(plainExcerpt('a'.repeat(100), 20), 'a'.repeat(19) + '…');
  assert.equal(plainExcerpt(''), '');
});
