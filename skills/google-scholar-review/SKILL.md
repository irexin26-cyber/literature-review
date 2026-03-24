---
name: google-scholar-review
description: Build management and economics literature review inputs by automatically querying Google Scholar through SerpAPI, exporting structured search results, and generating a review-ready evidence table plus draft outline. Use when the user asks for Google Scholar-based discovery, scholar-first corpus construction, or a quick literature review scaffold from Scholar search results.
---

# Google Scholar Review

Use this skill to run a Scholar-first review pipeline in one pass:

1. Query Google Scholar (via SerpAPI).
2. Save normalized records as JSON/CSV.
3. Generate an evidence table suitable for screening and synthesis.
4. Generate a draft review outline from the retrieved records.

## Required Setup

Set an API key before running scripts:

```bash
export SERPAPI_API_KEY="your_key"
```

On PowerShell:

```powershell
$env:SERPAPI_API_KEY="your_key"
```

## Core Script

- `scripts/google_scholar_review.py`
  - `search`: Query Google Scholar and save normalized JSON/CSV.
  - `outline`: Build a markdown outline from search output.
  - `pipeline`: Run `search` then `outline` in one command.

## Typical Workflow

```bash
python skills/google-scholar-review/scripts/google_scholar_review.py \
  pipeline \
  --query "digital transformation dynamic capabilities" \
  --workspace /path/to/review-workspace \
  --year-start 2018 \
  --year-end 2026 \
  --max-results 40
```

Artifacts are written to:

- `<workspace>/01_search/google_scholar_results.json`
- `<workspace>/01_search/google_scholar_results.csv`
- `<workspace>/03_screening/scholar_evidence_table.csv`
- `<workspace>/07_plan/google_scholar_outline.md`

## Decision Rules

- Prefer explicit query strings with constructs like `"A" AND "B"`.
- Keep one broad query plus 2-3 narrow follow-up queries.
- Use year bounds to control concept drift.
- Treat citation counts as prioritization signals, not quality proof.
- After outline generation, manually confirm theoretical lenses and contradictions before drafting full prose.

## References

- `references/query-patterns.md`
