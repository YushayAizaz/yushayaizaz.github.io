import test from 'node:test';
import assert from 'node:assert/strict';
import { archiveEventType, splitEventLedger } from '../../src/lib/events.ts';
import { matchesArchiveItem } from '../../src/lib/reading.ts';
import { pressBios } from '../../src/lib/press.ts';
import { bindBioCopy } from '../../src/scripts/copy-bio.ts';

const record = (id, type, date) => ({ id, data: { type, date: new Date(date), draft: false } });

test('the ledger shows nearest future gatherings first and recognition newest first', () => {
  const now = new Date('2026-11-15T12:00:00Z');
  const events = [
    record('later', 'upcoming-event', '2026-11-18'),
    record('award', 'award', '2026-11-14'),
    record('elapsed', 'upcoming-event', '2026-11-13'),
    record('nearer', 'upcoming-event', '2026-11-16'),
    record('at-cutoff', 'upcoming-event', now),
  ];
  const { upcoming, archive } = splitEventLedger(events, now);
  assert.deepEqual(upcoming.map(({ id }) => id), ['nearer', 'later']);
  assert.deepEqual(archive.map(({ id }) => id), ['at-cutoff', 'award', 'elapsed']);
  assert.equal(events[0].id, 'later');
});

test('appearance filter includes elapsed gatherings and excludes other recognition types', () => {
  const matches = (type, selected) => matchesArchiveItem('', [archiveEventType(type)], '', selected);
  assert.equal(matches('upcoming-event', 'past-event'), true);
  assert.equal(matches('past-event', 'past-event'), true);
  assert.equal(matches('award', 'past-event'), false);
  assert.equal(matches('award', 'award'), true);
  assert.equal(matches('publication', 'milestone'), false);
  assert.equal(matches('milestone', ''), true);
});

class CopyButton extends EventTarget {
  hidden = true;
  click() { this.dispatchEvent(new Event('click')); }
}

test('each copy button copies its displayed bio verbatim and clears its announcement', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  for (const { text } of pressBios) {
    const button = new CopyButton();
    const status = { textContent: '' };
    const clipboard = { writeText: t.mock.fn(async () => {}) };
    const cleanup = bindBioCopy(button, { textContent: text }, status, clipboard);
    assert.equal(button.hidden, false);
    button.click();
    await Promise.resolve();
    assert.deepEqual(clipboard.writeText.mock.calls[0].arguments, [text]);
    assert.equal(status.textContent, 'Copied to clipboard');
    t.mock.timers.tick(2500);
    assert.equal(status.textContent, '');
    cleanup();
    button.click();
    assert.equal(clipboard.writeText.mock.callCount(), 1);
  }
});

test('missing or rejected Clipboard API leaves a clear manual copy instruction', async () => {
  const choices = [undefined, { async writeText() { throw new Error('Denied'); } }];
  for (const clipboard of choices) {
    const button = new CopyButton();
    const status = { textContent: '' };
    const cleanup = bindBioCopy(button, { textContent: 'Visible bio text' }, status, clipboard);
    button.click();
    await Promise.resolve();
    assert.match(status.textContent, /Select the bio text to copy it/);
    cleanup();
  }
});
