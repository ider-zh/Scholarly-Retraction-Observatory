# Screening exclusion examples

## Scope and interpretation

Adds a bounded sample audit beneath the OpenAlex screening figure on the overview
route, including its existing screening deep link. RW-only views do not display
OA examples. No population, denominator, inclusion rule or source aggregate is
changed. This side-conversation change does not run, stop or publish the main
thread's geography pipeline.

The purpose is to demonstrate the actual exclusion mechanism and its limits,
not to manufacture proof that all exclusions are correct. Ten deterministic
examples cover known notices, suspected notices, identifier conflicts, non-article
types and the review subtype. In particular:

- `W3128835701`: PubMed identifies its DOI as a retraction notice and links the
  original paper separately: https://pubmed.ncbi.nlm.nih.gov/1502206/.
- `W4295766134`: a retracted original with a separate notice, excluded here because
  OA labels it review. PubMed includes both Journal Article and Review types:
  https://pubmed.ncbi.nlm.nih.gov/36158123/.
- `W4283031628`: title begins `Retracted:` but lacks identifier evidence. The
  sample does not establish whether it is a notice; the report explicitly warns
  that the heuristic can exclude a retracted original.
- Conflicting identifier evidence is reported as unresolved, not adjudicated.

These observations do not estimate a false-exclusion rate. They justify a later
independent, larger review if the owner wants to assess screening accuracy. The
current task does not silently change the screening policy.

## Reproduction and provenance

Run `python scripts/sample-screening-exclusions.py <frozen-run-directory>`.
It reads only manifest-listed completed identifier shards and the selected
original snapshot files for titles. Source file sizes and mtimes must still match
validation. SHA-256 of `screening-examples-v1/` + Work ID ranks each exclusion
stratum; the first two are selected, splitting excluded types into review/other.
Selection is independent of title plausibility. The complete screening counts
must equal the published figure before examples can be rendered.

The bounded sidecar `public/data/screening-examples.json` is separate from the
atomic snapshot directory so a geography rebuild cannot overwrite it. It carries
source manifest, scan configuration, role policy, cutoff dates and stratum sizes.
`src/report/screeningExamplesAsset.js` pins its size and SHA-256. Browser and
public-data checks validate the contract, fields, cap of 12, exclusion predicates
and current screening counts. A mismatch shows an unavailable state, not stale
examples. The existing 36 RW examples are unchanged; the new explicit sidecar
allowlist and separate cap do not permit raw snapshot tables or unbounded rows.
Both kinds of examples count toward the existing 2 MiB public-data budget.

## Reading design and checks

Before: the screening chart explains grouped counts but provides no record-level
evidence. Chosen design: a short interpretation boundary plus five expandable
reason groups; notification examples start open. Rejected alternative: ten
always-visible cards that would overwhelm the overview. Existing publication
tokens and typography are reused, with no new UI library.

Actual checks:

- `node --test tests/screening-examples.test.mjs tests/snapshot-sources.test.mjs`:
  all 7 passed.
- `python -m unittest discover -s tests -p test_screening_examples.py`: 2 passed.
- Isolated Vite production build to `/tmp/sro-screening-examples-build`: passed;
  no PPT regeneration, source publication, commit, push or deployment performed.
- Public-data guard passed for the local public directory and isolated build:
  36 existing RW examples plus 10 exclusion examples, 1,609,398 bytes at check time.
- Broader `tests/snapshot-*.test.mjs` plus the new tests: 59/62 passed; 3 existing
  Topic-hierarchy tests failed on the shared checkout's taxonomy data. No taxonomy
  files or data were changed by this task, and those failures were not repaired.
- Browser checks at local `http://127.0.0.1:5186/` cover 1440×900, 768×1024,
  390×844, RW/OA/joint selection, two existing slice links, grouped examples,
  uncertain-case disclosures, exact sample export, integrity failure and scoped
  axe checks. Final run passed all 6 groups with no page errors. The test explicitly
  reloads for the tampering check; same-hash navigation otherwise retains the
  already verified component, as intended.
- Initial axe review found links distinguishable only by color; explicit
  underlines fixed this. Desktop section and mobile uncertain-case screenshots
  were actually opened and inspected. Long expanded examples scroll vertically.

Before screenshots: `/tmp/sro-screening-examples/before-{desktop,mobile}.png`.
Confirmation artifacts: `/tmp/sro-screening-examples/confirm/`, including
`{desktop,tablet,mobile}-section.png`, `*-uncertain.png` and `checks.json`.
No physical-device, Safari, Firefox or deployed-site inspection was performed.
