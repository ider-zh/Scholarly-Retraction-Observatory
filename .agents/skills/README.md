# Project-local skills

- `html-ppt-skill` (skill name `html-ppt`): installed from https://github.com/lewislulu/html-ppt-skill at commit `f3a8435d3901697d5ac5e64d356c933637e43107`, using the Codex skill-installer download helper. The initial sparse Git attempt could not locate the root skill; archive installation succeeded. Upstream files and MIT license are intact. No npx hooks or extra runtime packages were executed. The v2 deck uses `templates/deck.html`, its cover / two-column / chart-bar / three-column layout patterns, `academic-paper`, and the local keyboard runtime; Chart.js and CDN fonts are deliberately not used.

- `research-report-design`: the user-supplied research reporting workflow; installation history is in `docs/OVERVIEW_REDESIGN_REVIEW.md`.
- `frontend-design`: installed from `anthropics/skills`, directory `skills/frontend-design`, pinned commit `34040c9c568585f6929bedeaad110ad08f079624`. Requested listing: https://www.skills.sh/anthropics/skills/frontend-design. Upstream: https://github.com/anthropics/skills/tree/34040c9c568585f6929bedeaad110ad08f079624/skills/frontend-design.

The repository's `AGENTS.md` directs report UI tasks to use frontend-design for visual decisions and research-report-design for evidence and statistical safeguards. Upstream skill files are kept intact, including accompanying license files. No third-party installation hooks or frontend runtime dependencies are required.
