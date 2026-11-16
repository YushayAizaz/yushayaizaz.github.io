import test from 'node:test';
import assert from 'node:assert/strict';
import {
  chapterOrder, dispatchNumberLabel, dispatchTagHref, entryHref,
  matchesArchiveItem, nextPlate, searchableText, tagKey,
} from '../../src/lib/reading.ts';

test('reader links preserve nested paths and encode URL characters', () => {
  assert.equal(entryHref('works', 'notes/café'), '/works/notes/caf%C3%A9/');
  assert.equal(entryHref('dispatches', 'photo-diary'), '/dispatches/photo-diary/');
  assert.equal(dispatchNumberLabel(1), 'No. 001');
  assert.equal(dispatchNumberLabel(1210), 'No. 1210');
  assert.equal(dispatchTagHref('Light & Shadow'), '/dispatches/?tag=light+%26+shadow');
});

test('dispatch search ignores accents and case and combines terms with a selected tag', () => {
  const searchable = searchableText('No. 003 · Fényi Café\nBudapest · River');
  const tags = ['River', 'Night Walk'].map(tagKey);
  assert.equal(matchesArchiveItem(searchable, tags, searchableText('cafe  BUDAPEST'), 'river'), true);
  assert.equal(matchesArchiveItem(searchable, tags, searchableText('river tokyo'), 'river'), false);
  assert.equal(matchesArchiveItem(searchable, tags, 'cafe', 'different'), false);
  assert.equal(matchesArchiveItem(searchable, tags, '', ''), true);
});

test('original works use exact category matches and clear back to all items', () => {
  assert.equal(matchesArchiveItem('', ['short-story'], '', 'short-story'), true);
  assert.equal(matchesArchiveItem('', ['short-story'], '', 'story'), false);
  assert.equal(matchesArchiveItem('', ['short-story'], '', ''), true);
});

test('plate keyboard navigation wraps and leaves unrelated keys alone', () => {
  assert.equal(nextPlate(0, 'ArrowLeft', 3), 2);
  assert.equal(nextPlate(2, 'ArrowRight', 3), 0);
  assert.equal(nextPlate(1, 'ArrowRight', 3), 2);
  assert.equal(nextPlate(1, 'Home', 3), 0);
  assert.equal(nextPlate(1, 'End', 3), 2);
  assert.equal(nextPlate(0, 'Tab', 3), undefined);
});

test('book excerpts sort by editorial order then chapter and keep the original array intact', () => {
  const excerpt = (id, order, chapterNumber) => ({ id, data: { order, chapterNumber } });
  const entries = [
    excerpt('later-order', 3, 1), excerpt('chapter-two-b', 2, 2),
    excerpt('chapter-two-a', 2, 2), excerpt('chapter-one', 2, 1),
  ];
  assert.deepEqual(chapterOrder(entries).map(({ id }) => id), [
    'chapter-one', 'chapter-two-a', 'chapter-two-b', 'later-order',
  ]);
  assert.equal(entries[0].id, 'later-order');
});
