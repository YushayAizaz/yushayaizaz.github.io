# Yushay Aizaz — Author Platform

The author platform includes the editorial homepage, dispatch and works archives, adaptive readers, book showroom, literary ledger, and press kit. It uses Pages CMS for editing and GitHub Actions for Instagram imports.

[Set up GitHub, Meta, Pages CMS and free hosting](docs/SETUP_AND_DEPLOYMENT.md). The launch branch uses a root GitHub Pages user site. Cloudflare Pages Free and Vercel Hobby remain options within their plan terms.

## Stack and version decision

- Astro **7.4.12**, using the Content Layer API introduced in Astro 5, static output and `ClientRouter` view transitions.
- Tailwind CSS 3.4, deliberately selected for the requested `tailwind.config.mjs` configuration model, with `@tailwindcss/typography` and PostCSS.
- A narrowly scoped `postcss-selector-parser` override applies the patched 6.1.5 release to the typography plugin.
- Locally served Cormorant Garamond, Source Serif 4 and JetBrains Mono fonts.
- Pages CMS, editing Markdown and media directly in GitHub.
- Python 3.12+, Requests, PyYAML and Pillow; GitHub Actions hourly.

The brief permits Astro 5+. An initial Astro 5.18.2 build passed, but its dependency audit reported security advisories. The delivered package uses a patched current release instead of claiming that an affected Astro 5 dependency is production-ready. Do not downgrade it without a new dependency review.

The requested schemas live in `src/content/config.ts`. Astro discovers them through `src/content.config.ts`, which re-exports the definitions. `glob` from `astro/loaders` is a supported loader, not the removed `Astro.glob()` API. The content loader calls `getCollection` and the readers call `render` from `astro:content`.

## Run locally

Use Node **24 LTS**, npm 9.6.5+ and Python 3.12+.

```bash
npm ci
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/validate_content.py
npm run test:frontend
npm run test:integration
npm run build
npm run dev
```

On Windows PowerShell, create the environment with `py -3 -m venv .venv`, then run `.venv\Scripts\Activate.ps1`. Use `python` instead of `python3` for the direct CLI commands. The npm convenience aliases use `python3`; the direct commands work on Windows too.

The book overview and press kit are public in the launch build. The five demonstration entries remain drafts. The public dispatch archive contains the imported Instagram posts. Enable the local draft preview to read the sample entries.

## Local draft preview and production publishing

Copy `.env.example` to `.env` and leave `INCLUDE_DRAFTS=true` to see the supplied samples in `npm run dev`. On Windows, use `Copy-Item .env.example .env`; on macOS/Linux, use `cp .env.example .env`. Restart the dev server after changing this setting. The examples contain no credentials.

```dotenv
INCLUDE_DRAFTS=true
```

The visible working-edition banner, individual Draft badges, preview archive counts and `noindex, nofollow` metadata make this mode explicit. Set the value to `false` or remove it to inspect the published edition locally.

`src/lib/content.ts` exposes two separate entry points:

- `editorialContent()` is the page helper: drafts are included only when the actual Astro command is `dev`, the environment is a development mode, and the flag is exactly `true`.
- `publishedContent()` always excludes drafts, even during local preview. Use it for future feeds, sitemaps and public metadata.

The Astro config injects a command-derived constant. Neither `INCLUDE_DRAFTS=true`, `NODE_ENV=development`, nor `astro build --mode development` can enable drafts in a build. `npm run preview` serves the already-built, published-only files. This is an editorial visibility rule, not authentication: do not expose a dev server containing private manuscripts to untrusted visitors. Public assets under `public/` remain public regardless of an entry’s draft flag.

The dev command uses `--ignore-lock` to stay in the foreground, including in agent-managed previews. It does not launch a separate background daemon. Start one dev process for this checkout and use Ctrl+C to stop it.

## Phase 2 reading experience

`EditorialLayout.astro` owns the head metadata, skip link, view transitions, masthead and footer. The first visit always uses Warm Literary Press, regardless of operating-system color preference. The toggle enables Nocturne Edition and saves the choice in `localStorage` under `yushay-reading-edition`.

The theme script runs before paint, carries the active edition across Astro page swaps, updates pressed state and theme-color metadata, and responds to other-tab storage changes. If storage is blocked, toggling and same-session navigation still work. With JavaScript disabled, the default light edition, navigation and native opening disclosures remain usable; the theme control stays hidden.

Homepage counts come from visible content at request time in development and build time in production. They are not a simulated counter. A newly imported post changes the counts on the next build. The featured dispatch favors `featured: true`, then the newest entry. The recent grid lists up to three dispatches; the selected-pages grid mixes works and field notes. The book section uses the visible overview, declared progress and up to two excerpts. The ledger chooses the nearest upcoming event, otherwise the latest dated event or milestone; an expired upcoming-event record is never called “next.” A static site updates its time-sensitive selection on the next build.

`DispatchCard.astro` accepts the actual collection entry shape used by the importer. More than one image produces `CAROUSEL · N PLATES` in both featured and recent cards. One image produces `PHOTOGRAPH · 1 PLATE`. Zero images produces a typographic “From the notebook” card with no empty `<img>` or broken source. All images use the local stored paths. No real Instagram credentials or fabricated imports are needed to test this behavior: the integration suite builds a disposable three-image fixture.

Set `SITE_URL` to the deployed HTTPS origin so Astro emits canonical URLs. Python scripts read process variables. Astro reads the local draft flag from `.env`.

## Archives and readers

- `/dispatches/` shows newest entries first with their existing dispatch numbers. Search matches titles, numbers, locations, topics, captions and body text. Topic pills combine with the search and can be cleared. The URL stores the search in `q` and the selected topic in `tag`.
- `/dispatches/<id>/` opens a centered reader for text-only entries. Photo entries place the plates beside the article on desktop and stack them above the body on mobile. Use the previous and next buttons, choose a thumbnail, or focus the gallery and use Left, Right, Home or End. With JavaScript disabled, the page displays every plate. Neighbor links follow the visible archive chronology.
- `/works/` filters by essay, poetry, short story or reflection. The `category` query parameter preserves the selection. `/works/<id>/` renders the full Markdown. Use blank lines between stanzas and two trailing spaces when an explicit Markdown line break is needed.
- `/book/` displays the overview, status, progress, themes and full excerpts. The excerpt list sorts by `order`, then `chapterNumber`. Its contents links open the chapter positions on the same page.

Both individual reader routes build their paths from `editorialContent()`. With the draft flag enabled in development, follow the titles or reading links from the homepage and archives. In a static build only published reader paths are generated. The example content includes one text-only dispatch, one poem and one essay. The integration tests supply disposable one-plate and three-plate entries for photo coverage.

`npm run test:integration` builds a temporary copy with no published entries and then with published fixtures. It checks links and local assets on all five top-level routes and the fixture readers, plus draft exclusion even when a build runs in development mode.

## Literary ledger and press kit

`/achievements/` lists upcoming gatherings by soonest date and the recognition archive by latest date. Once an upcoming gathering's timestamp passes, the next build lists it as an appearance. The archive accepts a shareable `type` filter and displays full event notes, metadata and photos from the Events & Recognition collection.

The [press kit](/achievements/#press-kit) includes two third-person bios, a copy button for each, speaking topics, and an Instagram contact link. Edit the published bio or topic text in `src/lib/press.ts` if the brief changes.

The launch bundle includes the author’s optimized portrait. To replace it, save an approved JPEG with the exact filename `public/images/uploads/yushay-aizaz-portrait.jpg` and commit it. In Pages CMS, use **Media → Editorial images → uploads** to place the same filename. The next build shows the portrait and its download link. Until then, the press kit displays a typographic monogram.

## Write from the terminal

```bash
python scripts/new_post.py dispatch "An evening by the river" --location Budapest --tag attention
python scripts/new_post.py poem "The window"
python scripts/new_post.py essay "The work of listening" --body-file essay.md
python scripts/new_post.py event "A confirmed reading" --event-type upcoming-event --date 2027-03-12 --location Budapest
python scripts/new_post.py excerpt "An opening conversation" --chapter 1 --synopsis "The opening encounter."
```

These commands create drafts. `--publish` requires a nonempty `--body-file`. The CLI never replaces an existing path and has no overwrite/force option. Real entries reserve their dispatch numbers even while in draft. Demonstration files whose names start with `2026-11-14-sample-` and whose `draft` value is `true` do not reserve numbers. The first real import starts at 1 when no other real entries exist.

The empty body in a new draft is an intentional authoring canvas, not placeholder prose. Poetry supports Markdown hard line breaks (two trailing spaces) and blank lines between stanzas.

## Edit in a browser

`.pages.yml` configures [Pages CMS](https://app.pagescms.org) for all four collections, rich-text bodies, source editing, draft switches and image uploads. It uses GitHub login and repository access; it does not require a CMS server or a paid database. Follow the [Pages CMS setup steps](docs/SETUP_AND_DEPLOYMENT.md#step-3--edit-through-pages-cms).

Uploaded media goes to `public/images` and is written into content as `/images/...`. Choose uploaded raster images (JPG, PNG, WebP, AVIF or GIF). Images imported from Instagram go in their own `public/images/dispatches/<id>/` folder.

The CMS requires a unique positive dispatch number for a new manually written dispatch. Automatic allocation is provided by the CLI and importer; Pages CMS cannot atomically compute a sequence number. Validation rejects duplicate numbers. Preserve `instagramId` when manually editing Markdown; the CMS presents import identity as read-only.

## Instagram sync contract

**Behold JSON feed** is the default source. The bundled feed is for `@yushayaizaz`. To change it, set the `BEHOLD_FEED_URL` process environment variable locally or the same **repository variable** in GitHub Actions. The scheduled and manual workflow runs use Behold without Meta secrets.

| Variable | Default | Purpose |
| --- | --- | --- |
| `BEHOLD_FEED_URL` | Bundled author feed | Override with another HTTPS feed from `feeds.behold.so`. |
| `INSTAGRAM_IMPORT_DRAFT` | `false` | Set to `true` to review new imports before publishing. |
| `SITE_URL` | unset | Actual HTTPS origin for canonical URLs. |

To use Instagram Login locally instead, supply `INSTAGRAM_ACCESS_TOKEN` and the numeric `INSTAGRAM_USER_ID` in your process environment. `INSTAGRAM_API_VERSION` defaults to `v27.0` for that mode. The importer reads only the process environment.

```bash
python scripts/sync_instagram.py --dry-run
python scripts/sync_instagram.py
```

`--dry-run` counts would-be imports without writing files or downloading media. A normal run numbers new posts from oldest to newest. Use `--feature-latest` to feature the newest entry in that run while preserving existing featured entries.

GitHub Actions checks the feed hourly at minute 0 UTC, plus manual runs. On successful import pushes it dispatches the GitHub Pages workflow. Behold Free updates its source once a day and includes 1,200 feed views per month. Hourly scheduled checks use up to 744 views in a 31-day month, with extra usage from manual requests and retries. [Behold pricing and limits](https://behold.so/pricing/)

### Preservation guarantees

1. Every existing Markdown file is treated as editorial property, even with `lockedForManualEdits: false`. No existing body, title, tags, frontmatter or local image is replaced.
2. Import IDs are checked against frontmatter, ID-bearing filenames, permalinks and `data/instagram-imports.json`. Renaming or deleting an imported article does not make it new again.
3. Do not delete the ledger when removing an imported article. Its retained ID is a tombstone. To intentionally reimport, remove the matching ledger record and the matching Markdown after taking your own backup. The importer never performs that action for you.
4. All images are downloaded and decoded/verified before the article is created. A missing child image, missing video poster, invalid image, oversize asset or network failure prevents a partial article from being published.
5. Single images, carousel covers, and every carousel child image are persisted locally. A cover that is also a slide uses that slide’s local copy. Videos and video children use locally saved poster thumbnails, with the original video available through the Instagram link. This is an image-based journal, not a video archive.
6. Behold imports use the pruned caption and editable hashtag tags. Caption copy preserves literal text and line breaks; HTML and Markdown control characters are escaped. Hashtags generate editable tags; the first meaningful line generates an editable title. No AI service or paid model is used.
7. Empty image descriptions are deliberately honest. The importer does not invent visual descriptions from captions; add accessible descriptions in the CMS. The future reader must handle empty alt text without using filenames as descriptions.
8. Files are published using an exclusive atomic link. A local OS lock serializes CLI/import writes, and GitHub Actions concurrency serializes scheduled jobs.
9. If an editor pushes while import is running, a non-fast-forward push fails. The disposable runner discards its candidate commit, checks out the current branch, and reruns the import up to three times. There is no force push and no automatic rebase over editorial changes.
10. Remote caption edits and deletions are not propagated. They must be reflected on the website by the author, deliberately.

An interrupted process can leave unused local images, but not a partially written Markdown file. Existing asset bytes are never silently changed. If a retry finds different bytes at an existing asset path, it stops for deliberate reconciliation.

## Cost and operational limits

The architecture has no mandatory paid dependency, but “$0/month forever” is not a promise any third-party platform can make. All external terms and allowances can change.

- Pages CMS currently offers a free hosted app and open-source software.
- Standard GitHub Actions runners are free for public repositories. Private repositories have included quotas; exceeding them is not an unlimited free service. Public Git history also exposes draft source. Use a private repository if unpublished work must remain private, monitor its included minutes, and disable paid overages.
- Public repository schedules may be disabled after 60 days without repository activity. Cron runs can be delayed or dropped. The manual workflow remains the recovery path; this is not an exact-time scheduler.
- If you use the optional local Instagram Login mode, [refresh its long-lived token](docs/SETUP_AND_DEPLOYMENT.md#refresh-the-token-before-it-expires) before expiry.
- Cloudflare Pages Free offers a provider subdomain within its free limits. Vercel Hobby limits use to personal, non-commercial projects. See the [hosting options](docs/SETUP_AND_DEPLOYMENT.md#step-4--host-the-site-and-request-builds-after-bot-commits).
- Branch rules must permit the bot's direct content commits for this workflow. A protected branch that rejects them will fail safely rather than bypass protection.
- Bot commits made with `GITHUB_TOKEN` do not trigger other push-based GitHub Actions. The sync job validates each candidate commit before pushing. The optional deploy hook requests a host build after a successful push. Check the hosting dashboard for completion.
- The production platform is published through GitHub Pages. The bundled Behold feed can be replaced through the repository variable without changing the code.

## Delivery phases

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Content models, CMS, CLI, Instagram import, automation, sample content and buildable foundation | Delivered |
| 2 | Global editorial layout, navigation, footer, persisted theme toggle, manifesto homepage and curated modules | Delivered |
| 3 | Dispatch archive/search/tags, split carousel reader, text-only reader, original works, poetry and book showroom | Delivered |
| 4 | Events, achievements, press kit, portrait support, Meta token setup, CMS login and deployment guide | Delivered |

## Primary references

- [Astro Content Layer](https://docs.astro.build/en/guides/content-collections/)
- [Astro 7 upgrade guide](https://docs.astro.build/en/guides/upgrade-to/v7/)
- [Astro security advisories](https://github.com/withastro/astro/security/advisories)
- [Pages CMS configuration](https://pagescms.org/docs/configuration/)
- [Pages CMS pricing and source](https://pagescms.org/)
- [Meta Instagram Media reference](https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/)
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [GitHub scheduled event behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GitHub token trigger behavior](https://docs.github.com/en/actions/concepts/security/github_token)
- [Vercel Hobby terms](https://vercel.com/docs/plans/hobby)
