# Phase 1 validation — 14 November 2026

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | 26 passed with Requests 2.33.0 and Pillow 13.0.0 |
| `python scripts/validate_content.py` | All six sample entries and local asset references validated |
| `npm run build` | Static build passed; Astro diagnostics: 0 errors, 0 warnings, 0 hints |
| `npm audit` | 0 known vulnerabilities after dependency updates and the scoped parser override |
| `pip-audit -r requirements.txt` | No known vulnerabilities found |
| Workflow YAML parsing | Both workflow files parsed successfully |
| CMS content coverage | Every sample frontmatter field has a configured editor field |

Regression coverage includes repeat-run stability; existing-file preservation with
both lock states; renamed and deleted posts; duplicate remote IDs; full carousel
child enumeration; mixed image/video albums; missing media; corrupt images;
actual image-format detection; incomplete downloads; read-only dry runs;
malformed frontmatter and ledgers; caption HTML escaping; CDN allowlisting;
pagination limits; rate-limit retries; atomic non-replacement; and CLI drafts.

The build uses Astro 7.4.12, Node 24.22.1 and Python 3.12.14 in the validation
environment. npm's lockfile is included. Dependency audits describe known
advisories at the time of the check, not a guarantee about future discoveries.

No live Meta API request, authenticated Pages CMS editing session, remote GitHub
Actions run, or hosting deployment has been performed. Those require the author's
account configuration. The complete editorial interface and visual QA are
reserved for the subsequent delivery phases. The Phase 1 page is a buildable
foundation page, not the finished homepage.
