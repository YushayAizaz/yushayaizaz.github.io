/** Pure policies shared by the Astro loader and dependency-free Node tests. */
export interface DatedEntry {
  id: string;
  data: { draft: boolean; date: Date };
}

export function allowDraftPreview(devServer: boolean, devMode: boolean, flag: unknown): boolean {
  return devServer === true && devMode === true && flag === 'true';
}

export function visibleEntries<T extends DatedEntry>(entries: T[], includeDrafts = false): T[] {
  return entries.filter((entry) => !entry.data.draft || includeDrafts);
}

export function newestFirst<T extends DatedEntry>(entries: T[]): T[] {
  return [...entries].sort((a, b) => b.data.date.getTime() - a.data.date.getTime() || a.id.localeCompare(b.id));
}

export function featuredEntry<T extends DatedEntry & { data: { featured: boolean } }>(entries: T[]): T | undefined {
  const sorted = newestFirst(entries);
  return sorted.find(({ data }) => data.featured) ?? sorted[0];
}

export function mediaLabel(images: readonly string[]): string {
  if (images.length > 1) return `CAROUSEL · ${images.length} PLATES`;
  return images.length === 1 ? 'PHOTOGRAPH · 1 PLATE' : 'FROM THE NOTEBOOK';
}

export function readingMinutes(body = ''): number {
  return Math.max(1, Math.ceil(body.trim().split(/\s+/u).filter(Boolean).length / 200));
}

export function plainExcerpt(body = '', limit = 300): string {
  const plain = body
    .replace(/!\[[^\]]*\]\([^)]*\)/gu, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/gu, '$1')
    .replace(/<[^>]+>/gu, '')
    .replace(/(^|\n)\s{0,3}#{1,6}\s+/gu, '$1')
    .replace(/[*_`]/gu, '')
    .replace(/\\([\p{P}\p{S}])/gu, '$1')
    .replace(/\s+/gu, ' ').trim();
  if (plain.length <= limit) return plain;
  const cut = plain.slice(0, limit - 1);
  const boundary = cut.lastIndexOf(' ');
  return `${boundary > limit / 2 ? cut.slice(0, boundary) : cut}…`;
}

export function formatDate(value: Date): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Europe/Budapest',
  }).format(value);
}

export function isUpcomingEvent(type: string, date: Date, now: Date): boolean {
  return type === 'upcoming-event' && date.getTime() > now.getTime();
}

export function selectEvent<T extends DatedEntry & { data: { type: string } }>(entries: T[], now = new Date()): T | undefined {
  const upcoming = entries
    .filter(({ data }) => isUpcomingEvent(data.type, data.date, now))
    .sort((a, b) => a.data.date.getTime() - b.data.date.getTime() || a.id.localeCompare(b.id));
  return upcoming[0] ?? newestFirst(entries.filter(({ data }) => data.date.getTime() <= now.getTime()))[0];
}

export function eventLabel(type: string, date: Date, now = new Date()): string {
  if (type === 'upcoming-event') return isUpcomingEvent(type, date, now) ? 'Next gathering' : 'From the events ledger';
  return ({ 'past-event': 'From the events ledger', award: 'Recognition', publication: 'In print', milestone: 'A writing milestone' } as Record<string, string>)[type] ?? 'From the ledger';
}
