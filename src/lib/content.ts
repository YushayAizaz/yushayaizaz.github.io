import { getCollection } from 'astro:content';
import { allowDraftPreview, newestFirst, visibleEntries } from './content-policy';

/** Set by the Astro config hook, not an environment variable a build can enable. */
export const includesDrafts = allowDraftPreview(
  __EDITORIAL_DEV_SERVER__,
  import.meta.env.DEV,
  import.meta.env.INCLUDE_DRAFTS,
);

async function loadContent(includeDrafts: boolean) {
  const [allDispatches, allWorks, allBook, allEvents] = await Promise.all([
    getCollection('dispatches'), getCollection('works'), getCollection('book'), getCollection('events'),
  ]);
  const dispatches = newestFirst(visibleEntries(allDispatches, includeDrafts));
  const works = newestFirst(visibleEntries(allWorks, includeDrafts));
  const book = visibleEntries(allBook, includeDrafts).sort((a, b) => a.data.order - b.data.order || a.id.localeCompare(b.id));
  const events = newestFirst(visibleEntries(allEvents, includeDrafts));
  const numbers = new Set<number>();
  for (const entry of dispatches) {
    // Match the importer's numbering rule when local preview includes demonstrations.
    const filename = entry.id.split('/').at(-1);
    if (entry.data.draft && filename?.startsWith('2026-11-14-sample-')) continue;
    if (numbers.has(entry.data.dispatchNumber)) throw new Error(`Duplicate visible dispatch number: ${entry.data.dispatchNumber}`);
    numbers.add(entry.data.dispatchNumber);
  }
  if (book.filter(({ data }) => data.kind === 'overview').length > 1) {
    throw new Error('Only one visible book overview is allowed.');
  }
  return { dispatches, works, book, events };
}

/** Always published-only: use for public feeds, sitemaps and metadata. */
export async function publishedContent() {
  return loadContent(false);
}

/** Use for pages and their static paths; a build can never include drafts. */
export async function editorialContent() {
  return { ...await loadContent(includesDrafts), includesDrafts };
}
