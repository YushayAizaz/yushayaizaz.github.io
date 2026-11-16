/** Build disposable content fixtures. Never edits the author's Markdown. */
import assert from 'node:assert/strict';
import { access, cp, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { constants } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const fixture = await mkdtemp(join(tmpdir(), 'yushay-site-'));
const astroPackage = JSON.parse(await readFile(join(root, 'node_modules/astro/package.json'), 'utf8'));
const cli = join(fixture, 'node_modules/astro', astroPackage.bin.astro);
const ignored = new Set(['node_modules', '.venv', 'dist', '.astro', '.cache', '.git', '__pycache__']);

async function copySource(from, to) {
  await mkdir(to, { recursive: true });
  for (const item of await readdir(from, { withFileTypes: true })) {
    if (ignored.has(item.name) || item.name === '.env' || (item.name.startsWith('.env.') && item.name !== '.env.example')) continue;
    if (item.isDirectory()) await copySource(join(from, item.name), join(to, item.name));
    else if (item.isFile()) await cp(join(from, item.name), join(to, item.name));
  }
}
function frontmatter(data, body) {
  // JSON objects are valid YAML 1.2; Astro's frontmatter parser accepts them.
  return `---\n${JSON.stringify(data, null, 2)}\n---\n\n${body}\n`;
}
async function build(extraArgs = [], nodeEnv = 'production') {
  const result = spawnSync(process.execPath, [cli, 'build', '--root', fixture, ...extraArgs], {
    cwd: fixture, encoding: 'utf8', timeout: 120_000,
    env: { ...process.env, INCLUDE_DRAFTS: 'true', NODE_ENV: nodeEnv, ASTRO_TELEMETRY_DISABLED: '1' },
  });
  if (result.status !== 0) throw Error(`Fixture build failed:\n${result.stdout}\n${result.stderr}`);
  return route('/');
}
function outputPath(pathname) {
  return join(fixture, 'dist', decodeURIComponent(pathname), 'index.html');
}
function route(pathname) {
  return readFile(outputPath(pathname), 'utf8');
}
async function verifyNoBrokenLocalLinks(html, pathname = '/') {
  const origin = 'https://fixture.invalid';
  const seen = new Set();
  for (const [tag] of html.matchAll(/<(?:a|img|script|link)\b[^>]*>/gi)) {
    const value = tag.match(/\s(?:href|src)="([^"]*)"/)?.[1];
    if (value === undefined) continue;
    assert.ok(value, `Empty link or source in ${pathname}: ${tag}`);
    const url = new URL(value.replaceAll('&amp;', '&'), origin + pathname);
    if (url.origin !== origin) continue;
    const key = url.pathname + url.hash;
    if (seen.has(key)) continue;
    seen.add(key);
    if (!url.pathname.endsWith('/')) {
      await access(join(fixture, 'dist', decodeURIComponent(url.pathname)));
      continue;
    }
    const target = url.pathname === pathname ? html : await route(url.pathname);
    if (url.hash) {
      const id = decodeURIComponent(url.hash.slice(1));
      assert.ok(target.includes(`id="${id}"`), `Missing section: ${value} from ${pathname}`);
    }
  }
}
function verifyPressBios(html) {
  assert.match(html, /id="press-kit"/);
  for (const id of ['short', 'long']) {
    assert.match(html, new RegExp(`<button[^>]*data-copy-bio[^>]*aria-label="Copy ${id} bio"[^>]*aria-controls="press-bio-${id}"`));
    assert.match(html, new RegExp(`id="press-bio-${id}"[^>]*data-bio-text`));
  }
  assert.equal((html.match(/data-copy-status role="status"/g) ?? []).length, 2);
  assert.match(html, /https:\/\/www\.instagram\.com\/yushayaizaz\//);
}
function verifyDraftsAbsent(html) {
  for (const sentinel of ['PRIVATE-DRAFT-SENTINEL', 'PRIVATE-DRAFT-TAG', 'Sample —', 'Sample &#8212;', 'data-entry-id="private-draft"', 'Private working edition']) {
    assert.equal(html.includes(sentinel), false, `Draft output leaked: ${sentinel}`);
  }
}

try {
  await copySource(root, fixture);
  // A physical copy keeps Astro's compiled component paths inside the fixture root.
  await cp(join(root, 'node_modules'), join(fixture, 'node_modules'), { recursive: true, mode: constants.COPYFILE_FICLONE });
  const dispatchDir = join(fixture, 'src/content/dispatches');
  await writeFile(join(dispatchDir, 'private-draft.md'), frontmatter({
    title: 'PRIVATE-DRAFT-SENTINEL', tags: ['PRIVATE-DRAFT-TAG'], dispatchNumber: 900, date: '2026-11-15', source: 'website', draft: true,
    captionExcerpt: 'PRIVATE-DRAFT-SENTINEL', featured: true, lockedForManualEdits: true,
  }, 'PRIVATE-DRAFT-SENTINEL'));
  await writeFile(join(fixture, 'src/content/works/private-work.md'), frontmatter({
    title: 'PRIVATE-DRAFT-SENTINEL', date: '2026-11-15', category: 'essay', readingTime: 1, draft: true,
  }, 'PRIVATE-DRAFT-SENTINEL'));
  await writeFile(join(fixture, 'src/content/events/private-event.md'), frontmatter({
    title: 'PRIVATE-DRAFT-SENTINEL', date: '2099-11-14', type: 'upcoming-event',
    description: 'PRIVATE-DRAFT-EVENT-SUMMARY', draft: true,
  }, 'PRIVATE-DRAFT-EVENT-BODY'));
  // Ensure the empty run covers the fallback even if the author has added a portrait locally.
  const portrait = join(fixture, 'public/images/uploads/yushay-aizaz-portrait.jpg');
  const launchOverview = join(fixture, 'src/content/book/overview.md');
  // Retain the launch overview in the first build, then replace it only in the disposable fixtures.
  await rm(portrait, { force: true });
  await writeFile(join(fixture, '.env'), 'INCLUDE_DRAFTS=true\n');
  const empty = await build();
  verifyDraftsAbsent(empty);
  await verifyNoBrokenLocalLinks(empty);
  assert.ok(empty.includes('A quiet page. An open invitation.'));
  assert.ok(empty.includes('No dispatches have been published yet.'));
  assert.ok(empty.includes('Some words ask for a little longer.'));
  assert.match(empty, /His evening interviews are a starting point/);
  assert.match(await route('/book/'), /I began the evening interviews/);
  for (const [path, message] of [
    ['/dispatches/', 'No dispatches yet'], ['/works/', 'No original works yet'], ['/book/', 'No excerpts yet'], ['/achievements/', 'No upcoming gatherings'],
  ]) {
    const html = await route(path);
    verifyDraftsAbsent(html);
    assert.ok(html.includes(message), `Missing empty state at ${path}`);
    assert.ok(!html.includes('data-archive-controls'));
    await verifyNoBrokenLocalLinks(html, path);
  }
  const emptyLedger = await route('/achievements/');
  assert.match(emptyLedger, /No archive entries yet/);
  assert.match(emptyLedger, /data-portrait-slot/);
  assert.doesNotMatch(emptyLedger, /Download press portrait|PRIVATE-DRAFT-EVENT/);
  verifyPressBios(emptyLedger);

  for (const path of [
    '/dispatches/private-draft/', '/works/private-work/',
    '/dispatches/2026-11-14-sample-evening-notebook/', '/works/2026-11-14-sample-the-space-between/',
    '/works/2026-11-14-sample-on-attention/',
  ]) await assert.rejects(access(outputPath(path)), { code: 'ENOENT' });
  console.log('PASS: five empty-content pages, press kit fallback and copy controls, and no static draft readers.');

  const assetDir = join(fixture, 'public/images/dispatches/90001');
  await mkdir(assetDir, { recursive: true });
  const tinyImage = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6zAAAAABJRU5ErkJggg==', 'base64');
  const images = [1, 2, 3].map(index => `/images/dispatches/90001/${index}.png`);
  for (let i = 1; i <= 3; i++) await writeFile(join(assetDir, `${i}.png`), tinyImage);
  await writeFile(join(dispatchDir, 'three-plates.md'), frontmatter({
    title: 'Three plates from the city', dispatchNumber: 901, date: '2026-11-15', source: 'instagram',
    instagramId: '90001', instagramUrl: 'https://www.instagram.com/p/FIXTURE90001/', images,
    imageAlts: ['A test image', '', ''], captionExcerpt: 'A published carousel fixture.', tags: ['city', 'Night Walk'],
    featured: true, draft: false, lockedForManualEdits: true,
  }, 'The opening of the carousel fixture.'));
  await writeFile(join(dispatchDir, 'text-only.md'), frontmatter({
    title: 'Words without a photograph', dispatchNumber: 1, date: '2026-11-14', source: 'website',
    captionExcerpt: 'A published text-only fixture.', images: [], draft: false, lockedForManualEdits: true,
  }, 'The opening of the text-only fixture.'));
  await writeFile(join(dispatchDir, 'one-plate.md'), frontmatter({
    title: 'One photograph at dusk', dispatchNumber: 903, date: '2026-11-13', source: 'website',
    images: [images[0]], draft: false,
  }, 'A single photograph.'));
  await writeFile(join(fixture, 'src/content/works/public-work.md'), frontmatter({
    title: 'A published poem', date: '2026-11-15', category: 'poetry', readingTime: 1, featured: true, draft: false,
  }, 'A first line.  \nA second line.\n\nA new stanza.\nA soft line break.'));
  await mkdir(join(fixture, 'src/content/works/notebook'), { recursive: true });
  await writeFile(join(fixture, 'src/content/works/notebook/public-essay.md'), frontmatter({
    title: 'A published essay', date: '2026-11-14', category: 'essay', readingTime: 2, draft: false,
  }, 'A full essay body with **emphasis**.'));
  await rm(launchOverview);
  await writeFile(join(fixture, 'src/content/book/public-overview.md'), frontmatter({
    title: 'A published book overview', date: '2026-11-15', kind: 'overview', synopsis: 'An approved synopsis.',
    status: 'drafting', progress: 40, thematicPillars: ['Listening'], draft: false,
  }, 'A full overview paragraph with *emphasis*.'));
  await writeFile(join(fixture, 'src/content/book/public-excerpt.md'), frontmatter({
    title: 'A published opening', date: '2026-11-15', kind: 'excerpt', chapterNumber: 1, order: 1,
    synopsis: 'An approved opening.', status: 'drafting', progress: 40, draft: false,
  }, 'An opening from the manuscript.\n\nA second paragraph that belongs in the full excerpt.'));
  await writeFile(join(fixture, 'src/content/book/a-later-chapter.md'), frontmatter({
    title: 'A later excerpt', date: '2026-11-15', kind: 'excerpt', chapterNumber: 2, order: 1,
    synopsis: 'A second approved passage.', status: 'drafting', draft: false,
  }, 'A second chapter body.'));
  await writeFile(join(fixture, 'src/content/events/public-event.md'), frontmatter({
    title: 'A confirmed future reading', date: '2099-11-15', type: 'upcoming-event',
    description: 'A published test event.', location: 'Budapest', organization: 'Test venue', draft: false,
  }, 'An event description.'));
  const eventFixtures = [
    ['later-event', 'upcoming-event', '2099-12-15', 'A later gathering'],
    ['expired-event', 'upcoming-event', '2001-09-10', 'An elapsed gathering'],
    ['past-event', 'past-event', '2001-08-09', 'An earlier appearance'],
    ['award-entry', 'award', '2002-08-03', 'Recognition fixture'],
    ['publication-entry', 'publication', '2002-07-01', 'Publication fixture'],
    ['milestone-entry', 'milestone', '2000-05-06', 'Milestone fixture'],
  ];
  for (const [id, type, date, title] of eventFixtures) {
    await writeFile(join(fixture, `src/content/events/${id}.md`), frontmatter({
      title, type, date, location: 'Budapest', organization: 'Fixture organization',
      description: 'A full event summary.', draft: false,
      ...(id === 'publication-entry' && {
        photos: [images[0]], photoAlts: ['Test event photograph'], externalUrl: 'https://example.com/publication',
      }),
    }, 'A rendered note with **emphasis**.\n\n[A link to the work](/works/notebook/public-essay/).'));
  }
  await writeFile(portrait, Buffer.from('/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDeooorjOw//9k=', 'base64'));
  // A build in development mode must still be draft-free: command, not mode, is authoritative.
  const populated = await build(['--mode', 'development'], 'development');
  verifyDraftsAbsent(populated);
  await verifyNoBrokenLocalLinks(populated);
  assert.ok(populated.includes('CAROUSEL · 3 PLATES'));
  assert.match(populated, /class="author-portrait-frame"/);
  assert.match(populated, /src="\/images\/uploads\/yushay-aizaz-portrait.jpg"/);
  assert.ok(populated.includes('FROM THE NOTEBOOK'));
  assert.ok(populated.includes('Words without a photograph'));
  assert.ok(populated.includes('A published poem'));
  assert.ok(populated.includes('A confirmed future reading'));
  assert.ok(populated.includes('Next gathering'));
  assert.ok(/<progress[^>]+value="40"/.test(populated));
  assert.ok(populated.includes('An opening from the manuscript.'));
  assert.ok((populated.match(/CAROUSEL · 3 PLATES/g) ?? []).length >= 2, 'Both featured and recent cards must show the badge');
  assert.ok(populated.includes('data-recent-dispatches'));
  assert.ok(populated.includes('data-curated-journal'));
  for (const href of ['/dispatches/three-plates/', '/works/public-work/', '/book/', '/achievements/', '/achievements/#press-kit']) {
    assert.ok(populated.includes(`href="${href}"`), `Missing homepage link to ${href}`);
  }

  const pages = {};
  for (const path of [
    '/dispatches/', '/dispatches/three-plates/', '/dispatches/text-only/', '/dispatches/one-plate/',
    '/works/', '/works/public-work/', '/works/notebook/public-essay/', '/book/', '/achievements/',
  ]) {
    const html = await route(path);
    verifyDraftsAbsent(html);
    await verifyNoBrokenLocalLinks(html, path);
    pages[path] = html;
  }
  const dispatchArchive = pages['/dispatches/'];
  assert.match(dispatchArchive, /No\. 901/);
  assert.match(dispatchArchive, /No\. 001/);
  assert.match(dispatchArchive, /type="search"/);
  assert.match(dispatchArchive, /data-filter="night walk"/);
  assert.match(dispatchArchive, /data-filter-clear/);
  assert.ok(dispatchArchive.indexOf('data-entry-id="three-plates"') < dispatchArchive.indexOf('data-entry-id="text-only"'));
  assert.ok(dispatchArchive.indexOf('data-entry-id="text-only"') < dispatchArchive.indexOf('data-entry-id="one-plate"'));

  const magazine = pages['/dispatches/three-plates/'];
  assert.match(magazine, /data-reader="photographic-dispatch"/);
  assert.match(magazine, /lg:sticky/);
  assert.equal((magazine.match(/<figure data-plate/g) ?? []).length, 3);
  assert.equal((magazine.match(/aria-label="Show plate /g) ?? []).length, 3);
  assert.match(magazine, /Plate 1 of 3/);
  assert.match(magazine, /Original dispatch on Instagram/);
  assert.match(magazine, /alt="A test image"/);
  assert.match(magazine, /href="\/dispatches\/\?tag=night\+walk"/);
  assert.match(magazine, /The opening of the carousel fixture/);
  assert.match(magazine, /rel="prev" href="\/dispatches\/text-only\/"/);
  assert.doesNotMatch(magazine, /rel="next"/);
  assert.match(pages['/dispatches/one-plate/'], /Plate 1 of 1/);
  assert.doesNotMatch(pages['/dispatches/one-plate/'], /data-plate-next/);

  const essay = pages['/dispatches/text-only/'];
  assert.match(essay, /class="reader-article essay-reader"/);
  assert.match(essay, /class="literary-prose drop-cap"/);
  assert.doesNotMatch(essay, /<editorial-plates/);
  assert.match(essay, /rel="prev" href="\/dispatches\/one-plate\/"/);
  assert.match(essay, /rel="next" href="\/dispatches\/three-plates\/"/);

  const workArchive = pages['/works/'];
  for (const category of ['essay', 'poetry', 'short-story', 'reflection']) assert.ok(workArchive.includes(`data-filter="${category}"`));
  const poem = pages['/works/public-work/'];
  assert.match(poem, /class="literary-prose poetry"/);
  assert.match(poem, /A first line\.<br\s*\/?>(?:\s*)A second line\.<\/p>/);
  assert.match(poem, /<p>A new stanza\.\nA soft line break\.<\/p>/);
  assert.doesNotMatch(poem, /class="literary-prose drop-cap"/);
  const prose = pages['/works/notebook/public-essay/'];
  assert.match(prose, /class="literary-prose drop-cap"/);
  assert.match(prose, /<strong>emphasis<\/strong>/);

  const showroom = pages['/book/'];
  assert.match(showroom, /A full overview paragraph with <em>emphasis<\/em>/);
  assert.match(showroom, /Writing the manuscript/);
  assert.match(showroom, /<progress[^>]+value="40"/);
  assert.match(showroom, /<li>Listening<\/li>/);
  assert.match(showroom, /A second paragraph that belongs in the full excerpt/);
  assert.match(showroom, /A second chapter body/);
  assert.ok(showroom.indexOf('id="excerpt-public-excerpt"') < showroom.indexOf('id="excerpt-a-later-chapter"'));

  for (const path of ['/dispatches/private-draft/', '/works/private-work/']) {
    await assert.rejects(access(outputPath(path)), { code: 'ENOENT' });
  }
  const ledger = pages['/achievements/'];
  verifyPressBios(ledger);
  assert.match(ledger, /id="upcoming"/);
  const [schedule, recognition] = ledger.split(/<section[^>]*id="recognition"/);
  assert.ok(schedule.indexOf('data-event-id="public-event"') < schedule.indexOf('data-event-id="later-event"'));
  assert.doesNotMatch(schedule, /data-event-id="expired-event"/);
  assert.doesNotMatch(recognition, /data-event-id="public-event"/);
  const archivedIds = [...recognition.matchAll(/data-event-id="([^"]+)"/g)].map((match) => match[1]);
  assert.deepEqual(archivedIds, ['award-entry', 'publication-entry', 'expired-event', 'past-event', 'milestone-entry']);
  assert.match(recognition, /data-filter-name="type"/);
  for (const type of ['past-event', 'award', 'publication', 'milestone']) assert.match(recognition, new RegExp(`data-filter="${type}"`));
  assert.equal((recognition.match(/data-filters="\[&quot;past-event&quot;\]"/g) ?? []).length, 2);
  assert.match(recognition, /A rendered note with <strong>emphasis<\/strong>/);
  assert.match(recognition, /alt="Test event photograph"/);
  assert.match(recognition, /href="https:\/\/example\.com\/publication"/);
  assert.match(ledger, /download="yushay-aizaz-portrait.jpg"/);
  assert.doesNotMatch(ledger, /data-portrait-slot|PRIVATE-DRAFT-EVENT/);
  console.log('PASS: readers and filters, ordered excerpts, event rollover and recognition filters, bio buttons, portrait download, all internal links, and draft exclusion.');
} finally {
  await rm(fixture, { recursive: true, force: true });
}
