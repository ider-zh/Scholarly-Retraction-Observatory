# Country grouping: Taiwan included in China

## Requested scope

The project owner explicitly requested that Taiwan (`TW`) be included in China
(`CN`) in the report's statistics and maps. This is a declared reporting group,
not a claim that the upstream snapshot already uses this coding. Other source
codes, including `HK` and `MO`, are unchanged by this request.

## Statistical contract

- Normalize `TW` to `CN` before deduplicating each paper's country set.
- A paper associated with both codes counts once in the combined China group.
- Apply the same grouping to the eligible publication denominators and their
  annual breakdowns; do not add previously published country totals or average
  their proportions.
- Recompute fractional country weights and collaboration categories from the
  grouped country sets so that they remain consistent with the new counting unit.
- Retain the existing population, role-screening, publication-year and observation
  cutoff rules. No source snapshot records are rewritten.
- The mainland and Taiwan map geometries reference the same combined `CN` row.
  Colors, tooltips, selections, tables and exports must agree on that row.
- Keep Natural Earth geometry unchanged. The statistical mapping is explicit;
  no other geographic aliases or territorial changes are inferred.

## Release and verification

The dimension scan processed all 2,446 manifest-listed Work files using eight
workers, six threads per worker and a 32 GB per-worker ceiling. It completed in
409.48 seconds; the new cache hash is
`34217a35755905607a7f2621c3438bb1d167eb0b3acc14886aecd44314f4207d`.

Independent audit (`/tmp/sro-country-dimension-audit.json`) passed: all Field and
journal cells are unchanged, other countries' full-count cells are unchanged,
no `TW` cells remain, and every combined China cell satisfies union bounds.
Other countries' fractional weights can change when the number of distinct
reporting groups on a shared paper decreases.

For the institution-country article denominator in 2000–2026:
`14,705,099 + 998,036 − 85,033 = 15,618,102` eligible papers. The subtraction is
the observed overlap, not an estimated correction. It demonstrates why simply
adding the previous country totals would double-count publications.

The screened flagged-paper count for the all-period institution-country map is
25,509 (`25,064 + 548 − 103`). The 2000–2026 publication cohort has
`n=25,502`, `N=15,618,102`, or approximately `0.1633%`. These are distinct time
scopes, not inconsistent totals. Both PPT maps retain their original scopes.

The report rejects old denominator-policy markers. The frontend checks matching
manifest/explorer grouping versions and rejects grouped releases containing a
standalone `TW` row. Existing `node=TW` country links resolve to the combined
`CN` group; map keyboard selection uses that same group. CSV exports include
the grouping version and method.

The map renderers also reject input containing a standalone `TW` row, rather
than silently assigning an old, unmerged release the combined group's color.

The first report rebuild exposed a pre-existing stale local taxonomy marker:
`taxonomy-cohorts-v1`, although the published report already contained four Topic
levels. The matching v2 scan is restored before final delivery; its config hash
`6192c923f9b3a18444d93dcd31d7890fc6e25d5f6488b014854a8f86556b11ff`
matches the previous published explorer provenance. This restores existing
analysis, rather than introducing another subject method.

Final grouped release: `oa-2026-06-26-796781847629`. The restored taxonomy scan
completed in 287.1 seconds. A recursive comparison confirms that all eight
non-geography chapters' chart-row values and the complete discipline explorer
match the previous release (excluding release IDs and chart-row ordering).
The old RW report and its samples retain their initial SHA-256 checksums.

Executed checks:

- `npm run build`: passed, including the public-data guard; existing bundle-size
  warning remains.
- `node --test tests/presentation*.test.mjs tests/publication-builds.test.mjs tests/snapshot-*.test.mjs`:
  81 passed.
- `npm test`: 65 Python tests passed.
- Dimension audit and final release audit:
  `/tmp/sro-country-dimension-audit.json`, `/tmp/sro-country-release-audit.json`.
- `git diff --check` and the original RW file fingerprint checks passed.

Concurrent work added a separate screening-examples asset and related guard/UI
changes during this task. Those edits were not removed or treated as part of
country grouping. The final build guard includes them and reports 2,026,377
bytes, 36 RW samples and 10 bounded exclusion examples.

Browser baseline: `/tmp/sro-country-merge-before/`. Initial country-map review:
`/tmp/sro-country-merge-review/` (12 map states across desktop, tablet and mobile;
matching fills, n/N, selection and export checks passed). Final screenshot
locations are `/tmp/sro-country-merge-confirm/` and
`/tmp/sro-country-merge-deck-confirm/`.

Final browser confirmation passed all 12 country-map states and all six complete
deck test groups: 15 slides at 1440×900, 768×1024 and 390×844, automated axe checks,
RW/OA/joint-source navigation, deep links, keyboard interaction and exports.
No page errors occurred. Desktop slides 13/14, tablet slide 13 and mobile slide 14
were visually inspected. The existing slide-14 layout still requires scrolling
to read the final limitations; no new overlap or unreachable content was found.

Only the local working tree and external analysis caches were updated. No commit,
GitHub push or deployment was performed.

Prior map review documents describe the preceding exact-code-only release and
do not describe this newly requested reporting group.
