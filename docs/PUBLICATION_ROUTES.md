# Publication routes

All paths below are relative to the deployment root, including deployments under a repository directory.

| Publication | Canonical entry | Shareable detail |
| --- | --- | --- |
| Publication index | `/` | Three publication entries and their build timestamps |
| Report v1 | `/reports/v1/` | Tab hash, for example `#/disciplines` |
| Report v2 | `/reports/v2/` | Chapter hash, for example `#/time?sources=rw` |
| Presentation v2 | `/slides/v2/` | Slide hash, for example `#/13` |

The v2 overview with both sources is the default, so it needs no hash or `sources` parameter. A single source, slice, discipline node and other supported analysis parameters remain explicit in the hash. Existing validation and statistical contracts are unchanged. The share button copies the current address; unsupported clipboard environments offer a manual-copy fallback.

## Compatibility

- `/#/report-v1` redirects to `/reports/v1/`.
- `/#/snapshot/overview?sources=rw%2Coa` redirects to `/reports/v2/`.
- `/#/snapshot/time?sources=rw&slice=T1%2FB-retracted` redirects to `/reports/v2/#/time?sources=rw&slice=T1%2FB-retracted`.
- `/presentation-v2/index.html?preview=1#/13` redirects to `/slides/v2/?preview=1#/13`.
- Report v2 continues accepting legacy `#/snapshot/...` chapter hashes.

Redirects run in the browser and preserve the relevant query/hash state. They do not require server-side rewrite rules. The old presentation directory remains available for existing links.

## Build and verification

`npm run build` creates real `dist/reports/v1/index.html`, `dist/reports/v2/index.html` and `dist/slides/v2/index.html` entries. The reports share the existing compiled assets and public data at the deployment root. Vite development serves the same entry paths; the presentation alias uses its existing source directory.

Route tests: `node --test tests/publication-routes.test.mjs tests/presentation.test.mjs tests/publication-builds.test.mjs`.

Browser acceptance: serve `dist` as static files, then run `scripts/check-publication-routes-browser.mjs`. Set `PLAYWRIGHT_MODULE` and `CHROMIUM_PATH` for externally installed Playwright/browser binaries, `REPORT_QA_URL` for the static server root, and `REPORT_QA_OUT` for screenshot output. The check covers refresh, legacy redirects, source/slice state, copying links, presentation evidence links and desktop/tablet/mobile rendering.

## Local acceptance — 2026-09-29

- Production build and public-data boundary checks passed; published aggregates were unchanged.
- All 93 Node tests passed.
- Chromium checks passed on a plain static server at both `/` and `/project/`, and on the Vite development server.
- Screenshot sizes: 1440×900, 768×1024 and 390×844, covering the index, both reports and the presentation. Local evidence: `/tmp/sro-publication-routes/`, `/tmp/sro-publication-project/` and `/tmp/sro-publication-dev/`.
- Report v1 tab reload/sharing, report v2 RW/OA/combined selections, an existing slice deep link, legacy redirects and presentation evidence navigation passed. Browser runs reported no page errors or HTTP error responses.
- These checks verify the local checkout and build, not the hosting provider's deployment status.
