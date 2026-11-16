import { isUpcomingEvent, newestFirst, type DatedEntry } from './content-policy.ts';

export const eventTypes = {
  'past-event': 'Appearance',
  award: 'Award',
  publication: 'Publication',
  milestone: 'Milestone',
} as const;

type ArchivedType = keyof typeof eventTypes;
type EventType = ArchivedType | 'upcoming-event';

export function archiveEventType(type: EventType): ArchivedType {
  return type === 'upcoming-event' ? 'past-event' : type;
}

export function splitEventLedger<T extends DatedEntry & { data: { type: EventType } }>(entries: T[], now: Date) {
  const upcoming: T[] = [];
  const archive: T[] = [];
  for (const entry of entries) {
    (isUpcomingEvent(entry.data.type, entry.data.date, now) ? upcoming : archive).push(entry);
  }
  upcoming.sort((a, b) => a.data.date.getTime() - b.data.date.getTime() || a.id.localeCompare(b.id));
  return { upcoming, archive: newestFirst(archive) };
}
