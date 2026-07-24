# Supabase setup — store every posting raw, then decode

## Why Supabase, and why raw-first

Two rules this pipeline lives by:

1. **Every scraped posting lands in Postgres COMPLETE (full raw JSON) before any analysis.** Storage is free; re-pulling and re-paying (in time or credits) is not. When you improve a prompt next month, you re-decode from the raw rows instead of re-scraping.
2. **The raw payload sits in the row, beside the identifiers** (company + posting URL) — so a teammate can open the table and read exactly what the scraper saw. No mystery pipelines.

Supabase gives you hosted Postgres + a REST API (PostgREST) out of the box, so the scripts here need nothing but `requests`.

## Setup (5 minutes)

1. Create a free project at [supabase.com](https://supabase.com) → note the **Project URL** (`https://<ref>.supabase.co`).
2. Project Settings → API → copy the **service_role key** (server-side only — it bypasses RLS; never ship it to a browser).
3. Open the **SQL Editor**, paste [`sql/schema.sql`](../sql/schema.sql), run it.
4. Fill `.env`:

```bash
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SERVICE_KEY=eyJ...        # service_role
BLITZ_API_KEY=blitz_...
ANTHROPIC_API_KEY=sk-ant-...
```

## The schema (3 tables)

| Table | Grain | Holds |
|---|---|---|
| `accounts` | one row per target company | name, LinkedIn URL, status, posting count |
| `job_postings` | one row per posting | title, date, url + **`raw` JSONB (the complete Blitz object)** + `decoded` JSONB (Claude's per-posting extraction) |
| `account_briefs` | one row per account | the rolled-up brief: stack, direction, budget, hierarchy, strongest movement, ICP score + reasoning, outreach draft |

The flow writes left to right: `pull_jobs.py` fills `accounts` + `job_postings.raw`; `research.py` fills `job_postings.decoded` then `account_briefs`.

## Querying your results

```sql
-- top accounts by score
select company_name, icp_score, strongest_movement
from account_briefs order by icp_score desc nulls last limit 25;

-- every posting that mentions a tool you replace (raw, server-side ILIKE)
select a.company_name, p.job_title, p.date_posted
from job_postings p join accounts a on a.id = p.account_id
where p.raw->>'description' ilike '%kubernetes%';

-- accounts with a hiring spike (many fresh postings)
select a.company_name, count(*) n
from job_postings p join accounts a on a.id = p.account_id
where p.date_posted > now() - interval '30 days'
group by 1 having count(*) >= 5 order by n desc;
```

## Production notes

- **RLS:** the schema enables row-level security with no public policies — only the service key (your scripts) can read/write. Fine for a single-team pipeline.
- **Idempotency:** `job_postings` has a unique key on `(account_id, posting_key)`; re-running the pull upserts instead of duplicating.
- **Scale:** 1,000 accounts × ~30 postings ≈ 30k rows ≈ well inside the free tier.
- **Automation:** once the pilot looks right, schedule `pull_jobs.py` weekly (cron, GitHub Actions, or a Supabase Edge Function) so new postings flow in and only fresh rows get decoded.
