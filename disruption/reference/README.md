# Small-graph correctness oracle

This dependency-free Python implementation is deliberately slow and intended only
for tiny synthetic graphs. It is not the full-graph production engine and does not
establish production provenance, compression, crash recovery or coverage guarantees.

Run from the repository root:

```sh
python -m unittest discover -s disruption/reference -p 'test_*.py' -v
python -m disruption.reference.oracle tiny-works.json --snapshot-date 2026-06-26
```

Input is a JSON array with `id` (OpenAlex URL or `W123`), `year` (integer or null),
`referenced_works` (list of IDs or null), and optional `cited_by_count`. Output includes
canonical-edge audits, all-time indegree, dense annual observed counts and both window
policies. All candidate nodes are retained. Date precision and publication-date
conflicts are not modeled: the input contract supplies publication years only.

The CLI refuses more than 10,000 nodes. Normal tests use 15 or fewer. Counts are exact
distinct-Work counts; independent incoming and neighborhood paths check partition
identities. Missing years/unobservable windows are not zero-filled. Internal
inconsistency yields warnings, not score rewriting or publication blocking.

Tests implement the hand graph in `../ACCEPTANCE.md`, including duplicate references,
self-loops, dangling IDs, same-year observation, unknown/invalid years, maturity,
zero versus unobservable, degenerate formula behavior and warning-only mismatches.
They do not claim the entire production acceptance plan has been executed.
