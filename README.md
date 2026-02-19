# HF Papers Archive

A fully automated archive for Hugging Face Daily Papers.

It crawls papers from `https://huggingface.co/papers/date/YYYY-MM-DD`, stores normalized JSON records, generates bilingual summaries (EN + ZH), builds search indexes, and publishes a static Next.js website on GitHub Pages.

## Current Status

- Tagged releases: `v0.1`, `v0.3.1`, `v0.3.2`
- Main branch includes additional hardening after `v0.3.2` (dedupe + release-time visibility gating)

## Core Features

- Daily crawler (Python 3.11, `requests` + `beautifulsoup4` + `lxml`)
- Per-paper archival JSON under date folders
- Fields per paper:
  - `title`
  - `authors`
  - `abstract`
  - `summary_en`
  - `summary_zh`
  - `hf_url`
  - `arxiv_url`
  - `arxiv_pdf_url`
  - `github_url`
  - `upvotes`
  - `fetched_at`
- Translation pipeline:
  - `dummy` translator (works without API keys)
  - `openrouter` translator (default model: `moonshotai/kimi-k2.5`)
  - Auto-synthesize `summary_en` from `abstract` when `summary_en` is missing
- Search and index generation:
  - `data/index.json`
  - `data/search_index.json`
  - `data/dates/<date>.json`
- Static website (Next.js export) with:
  - date-based browsing
  - full-text search (title/authors/abstract/summaries)
  - bilingual summary toggle
  - per-paper detail pages
  - daily Overview panel
- Automation via GitHub Actions + GitHub Pages

## Important Runtime Rules

- Weekend skip: crawler skips Saturday/Sunday by default (can be overridden)
- Rate-limit friendly crawling:
  - randomized sleep between papers
  - retries with backoff
  - skip already complete records
- Cross-date dedupe in index build:
  - one visible record per `paper_id`
  - keeps earliest date as canonical display date
  - merges richer fields from duplicates
- Release-time visibility gate (default):
  - timezone: `Asia/Shanghai` (GMT+8)
  - release time: `08:00`
  - delay days: `1`
  - effect: papers for `YYYY-MM-DD` are not exposed in site indexes until `YYYY-MM-(DD+1) 08:00`

## Repository Layout

```text
hf-papers-archive/
  scripts/
    fetch_daily.py
    translate.py
    build_index.py
    backfill_range.py
    migrate_paper_layout.py
  data/
    papers/
    dates/
    index.json
    search_index.json
  site/
    app/
    components/
    lib/
    scripts/sync-data.mjs
    package.json
  .github/workflows/
    daily.yml
  requirements.txt
  README.md
```

## Quick Start (Local)

### 1) Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
npm install --prefix site
```

### 2) Fetch one day

```bash
python3 scripts/fetch_daily.py --date 2026-02-18 --skip-existing-complete
```

Optional (weekend override):

```bash
python3 scripts/fetch_daily.py --date 2026-02-15 --allow-weekend
```

### 3) Translate summaries

Auto mode (uses OpenRouter only if key is present):

```bash
export OPENROUTER_API_KEY=<your_key>
export OPENROUTER_MODEL=moonshotai/kimi-k2.5
python3 scripts/translate.py --provider auto --date 2026-02-18 --workers 6
```

### 4) Build index

```bash
python3 scripts/build_index.py
```

Optional visibility overrides:

```bash
export ARCHIVE_TIMEZONE=Asia/Shanghai
export ARCHIVE_RELEASE_HOUR=8
export ARCHIVE_RELEASE_MINUTE=0
export ARCHIVE_RELEASE_DELAY_DAYS=1
python3 scripts/build_index.py
```

### 5) Build static site

```bash
npm run build --prefix site
```

Output directory: `site/out`

### 6) Run site locally

Dev mode:

```bash
npm run dev --prefix site
```

Static preview example:

```bash
cd site/out && python3 -m http.server 4173
```

## Date-Range Backfill

Run full day-by-day pipeline (`fetch -> translate -> build index`):

```bash
python3 scripts/backfill_range.py \
  --start 2026-02-01 \
  --end 2026-02-19 \
  --provider auto \
  --workers 6 \
  --skip-existing-complete
```

## Data Schema

Example: `data/papers/2026-02-18/2602.14111.json`

```json
{
  "date": "2026-02-18",
  "paper_id": "2602.14111",
  "title": "Paper Title",
  "authors": ["Author A", "Author B"],
  "abstract": "...",
  "summary_en": "...",
  "summary_zh": "...",
  "hf_url": "https://huggingface.co/papers/2602.14111",
  "arxiv_url": "https://arxiv.org/abs/2602.14111",
  "arxiv_pdf_url": "https://arxiv.org/pdf/2602.14111",
  "github_url": "https://github.com/org/repo",
  "upvotes": 42,
  "fetched_at": "2026-02-19T00:12:34.123456+00:00"
}
```

## GitHub Actions Deployment

Workflow: `.github/workflows/daily.yml`

### Trigger modes

- `schedule`: daily at `00:00 UTC` (which is `08:00 GMT+8`)
- `workflow_dispatch`: manual run

### Workflow behavior

1. Resolve target date (default: previous day in selected timezone)
2. Run single-day pipeline with skip-existing optimization
3. Rebuild indexes
4. Commit `data/` only if changed
5. Build Next.js static site
6. Deploy to GitHub Pages

### Required repository settings

- `Settings -> Pages -> Source`: `GitHub Actions`
- `Settings -> Actions -> General -> Workflow permissions`: `Read and write permissions`

### Secrets

- `OPENROUTER_API_KEY` (required for real translation and AI Overview)
- `OPENROUTER_MODEL` (optional)
- `OPENROUTER_SUMMARY_MODEL` (optional)

## Release Notes

### v0.1

- Initial end-to-end MVP
- Daily fetch, JSON archive, index build, static site, Pages workflow

### v0.3.1

- OpenRouter-based translation flow stabilized
- Translation concurrency introduced (`--workers`, default 6)
- Prompt quality improvements for translation and overview generation

### v0.3.2

- UI/visual refinements and icon updates
- Home/detail page usability improvements
- Deployment flow polished for GitHub Pages

### Post-v0.3.2 (main branch updates)

- Date alignment fixes for display and daily scheduling
- Per-day folder layout adopted for paper JSON files
- Backfill and migration utilities added
- Deduplication across dates in index build
- Release-time visibility gate to prevent early exposure of next-date content
- Additional skip-existing logic to reduce redundant crawling/translation and lower rate-limit risk

## Notes

- If source page structure changes, parser fallbacks try to keep the pipeline resilient.
- Missing fields are allowed; the pipeline should not crash because of partial extraction.
- For production automation, keep translation worker count conservative (`2-6`) to reduce API throttling risk.
