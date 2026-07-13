# Lead Data Pipeline

Pulls form submissions, tracked phone calls, and Google Search Console data for a set of WordPress sites and upserts everything into Supabase. Runs every 12 hours on GitHub Actions. The data feeds a dashboard that compares how automated landing pages perform against the rest of each site.

## How it works

`main.py` loads site configs from environment variables and runs six jobs:

- `extract_automation_entries.py` pulls Gravity Forms entries from automation forms (last 7 days)
- `extract_all_entries.py` pulls every other Gravity Forms entry, skipping automation forms and anything before each site's cutoff date
- `get_non_automation_leads.py` pulls all form entries from the past month across every site
- `extract_calls.py` pulls CallTrackingMetrics calls, keeping only calls to each site's tracking number that lasted 30+ seconds
- `get_search_console_performance.py` pulls GSC page performance for automation pages (matched by regex)
- `get_keyword_rankings.py` pulls GSC keyword rankings for the last 90 days

The form and call jobs run in parallel. The two GSC jobs run sequentially because Google's API drops connections under parallel load. Everything yields batches of ~100 rows so memory stays flat, and each batch is upserted with a conflict key so reruns don't create duplicates. At the end, a direct Postgres connection calls `refresh_keyword_changes()` since the query is too slow for Supabase's RPC timeout.

## Setup

1. Clone the repo and install dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your values. The site lists are JSON strings, see the example file for the expected shape of each one.

3. Create the Supabase tables: `gf_entries`, `all_gf_entries`, `all_past_month`, `ctm_calls`, `search_console`, and `gsc_keyword_rankings`, plus a `refresh_keyword_changes()` SQL function. Column names match the row dicts built in each module.

## Usage

Run locally:

```
python main.py
```

For scheduled runs, add every variable from `.env.example` as a GitHub Actions secret. The workflow in `.github/workflows/pipeline.yml` runs every 12 hours and can also be triggered manually from the Actions tab.
