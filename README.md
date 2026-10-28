# Job Posting Intel

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/jaizendra-netizen/job-posting-intel)

**Extract intent from job postings with Claude + Blitz API.**

> Built and maintained by [OneGTMLab](https://www.onegtmlab.dev). Blitz API review and the full GTM tool directory: https://www.onegtmlab.dev/tool-directory

Job postings are the highest-signal account-research source that exists. A single posting tells you the real tech stack (tools named in requirements), where the company is heading (new roles = new initiatives), the budget (comp ranges × open-role count), the org hierarchy (who the role reports to), and the pain (the responsibilities section, written by the buyer themselves).

BuiltWith shows you the website. **Job postings show you the roadmap.**

This repo is the complete, free pipeline:

```
account list ──► Blitz API ──► Supabase (raw postings) ──► Claude ──► ranked accounts + outreach drafts
                 (pull)         (store)                    (decode · map · score · draft)
```

Intent platforms charge $20k+/year for this layer. This runs a 1,000-account sweep in minutes for $0 on Blitz's unlimited plan (free trial covers pilots).

---

## The method (do it in this order)

| # | Step | Tool | What happens |
|---|------|------|--------------|
| 1 | **Pull** | Blitz API | Every job posting from the last 90 days, per account. Server-side keyword filters, 1 call per company, cursor pagination. |
| 2 | **Store** | Supabase | Every posting lands raw (full JSON) in Postgres **before** any analysis. Storage is cheap; re-pulling is not. |
| 3 | **Decode** | Claude (Sonnet) | Each posting → structured intel: tools in requirements, seniority, comp, reports-to, responsibilities. |
| 4 | **Map** | Claude (Sonnet) | Postings roll up into one brief per account: stack · direction · budget · hierarchy · strongest movement. |
| 5 | **Score** | Claude (Sonnet) | Every account scored 0–5 on fit × movement × budget against *your* ICP. |
| 6 | **Draft** | Claude | Outreach for the 4s and 5s that opens with the movement, not a pitch. |

**Pilot first.** Run 25 accounts end to end before the full list. Check the decodes by hand. Only then scale.

**Never use regex/keyword matching for the judgment calls** (steps 3–5). Pattern-matching on titles gets seniority and intent wrong constantly. The decode must read the full posting text with an LLM. Regex is fine only for mechanical steps (URL cleaning, dedup keys).

---

## Quickstart

```bash
git clone https://github.com/onegtmlab/job-posting-intel.git
cd job-posting-intel
pip install requests

cp .env.example .env      # add your three keys

# 1. Create the tables (paste sql/schema.sql into the Supabase SQL editor)

# 2. Pull postings for your account list into Supabase
python scripts/pull_jobs.py accounts.csv        # csv: company_name,company_linkedin_url

# 3. Decode + brief + score with Claude
python scripts/research.py
```

`accounts.csv` needs just two columns: `company_name,company_linkedin_url`.

---

## Repo map

| Path | What it is |
|------|-----------|
| [`docs/BLITZ_ENDPOINTS.md`](docs/BLITZ_ENDPOINTS.md) | Every Blitz API endpoint, with the two job-posting endpoints documented in depth (payloads, filters, pagination, gotchas). |
| [`docs/SUPABASE_SETUP.md`](docs/SUPABASE_SETUP.md) | Supabase project setup, the schema, and why raw-first storage matters. |
| [`sql/schema.sql`](sql/schema.sql) | Three tables: `accounts`, `job_postings` (raw JSONB), `account_briefs`. |
| [`scripts/pull_jobs.py`](scripts/pull_jobs.py) | Account list → Blitz `/v2/jobs/company` → Supabase. Cursor pagination + 5 rps rate-limit handled. |
| [`scripts/research.py`](scripts/research.py) | Postings → Claude Sonnet (decode → brief → score) → `account_briefs`. |
| [`prompts/01_technographic_decode.md`](prompts/01_technographic_decode.md) | The per-posting decode prompt (technographic data extraction). |
| [`prompts/02_intent_brief.md`](prompts/02_intent_brief.md) | The per-account intent-brief prompt. |
| [`prompts/03_score.md`](prompts/03_score.md) | The ICP scoring prompt. |
| [`prompts/04_outreach.md`](prompts/04_outreach.md) | The movement-first outreach prompt. |

## Real decodes this produced (anonymized)

- A ~600-person healthcare AI company opened **6 security roles at once**, every posting saying *"one of the first engineers on the security team"* → an entire security org being built from scratch; every tool decision still open.
- A ~1,400-person fintech asks the new hire to *"define governance and controls for Agentic AI Workflows and Non-Human Identities"* → rolling out AI agents; nobody secures them yet.
- A ~3,300-person market-intelligence company is hiring an AI Security Analyst to hunt *"shadow AI and rogue agent activity"* → the problem is already loose inside.
- A ~2,600-person revenue-AI company opened a *"Head of AI Security"* seat → new function at leadership level; budget approved.

You see **why** they are hiring, not just that they are hiring. Outreach that opens with the movement gets answered.

## Requirements

- [Blitz API](https://www.blitz-api.ai) key — free trial gives 1,000 credits; unlimited plan makes every endpoint free
- [Supabase](https://supabase.com) project — free tier is plenty
- [Anthropic API](https://console.anthropic.com) key — Sonnet for bulk decode, ~$1–3 per 1,000 postings

## License

MIT — take it, run it, adapt it to your ICP.

---

Built by [OneGTMLab](https://www.onegtmlab.dev). Works for any ICP; sharpest for dev tools, cybersecurity, and software-development companies, whose postings name their exact stack.

More free GTM systems and tool reviews: [onegtmlab.dev/tool-directory](https://www.onegtmlab.dev/tool-directory).
