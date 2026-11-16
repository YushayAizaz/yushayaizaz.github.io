export const workCategories = {
  essay: 'Essay',
  poetry: 'Poetry',
  'short-story': 'Short story',
  reflection: 'Reflection',
} as const;

export function entryHref(collection: 'dispatches' | 'works', id: string): string {
  return `/${collection}/${id.split('/').map(encodeURIComponent).join('/')}/`;
}

export function dispatchNumberLabel(number: number): string {
  return `No. ${String(number).padStart(3, '0')}`;
}

export function tagKey(tag: string): string {
  return tag.normalize('NFKC').trim().toLowerCase();
}

export function dispatchTagHref(tag: string): string {
  return `/dispatches/?${new URLSearchParams({ tag: tagKey(tag) })}`;
}

export function searchableText(text: string): string {
  return text.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase().replace(/\s+/gu, ' ').trim();
}

export function matchesArchiveItem(searchText: string, filters: readonly string[], query: string, selected: string): boolean {
  if (selected && !filters.includes(selected)) return false;
  return query.split(' ').every((word) => searchText.includes(word));
}

export function nextPlate(index: number, key: string, count: number): number | undefined {
  if (key === 'ArrowLeft') return (index - 1 + count) % count;
  if (key === 'ArrowRight') return (index + 1) % count;
  if (key === 'Home') return 0;
  if (key === 'End') return count - 1;
  return undefined;
}

export function chapterOrder<T extends { id: string; data: { order: number; chapterNumber?: number } }>(entries: T[]): T[] {
  return [...entries].sort((a, b) => a.data.order - b.data.order
    || (a.data.chapterNumber ?? 0) - (b.data.chapterNumber ?? 0)
    || a.id.localeCompare(b.id));
}
