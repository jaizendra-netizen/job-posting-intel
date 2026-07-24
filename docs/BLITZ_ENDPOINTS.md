# Blitz API — Endpoint Reference (job-postings focus)

- **Base URL:** `https://api.blitz-api.ai`
- **Auth:** every request needs the `x-api-key: <YOUR_KEY>` header (get a key at [app.blitz-api.ai](https://app.blitz-api.ai)). Never put the key in client-side code.
- **Rate limit:** 5 requests/second **per endpoint** (each endpoint has its own budget).
- **Pricing:** free trial = 1,000 credits (1 credit per job returned). Unlimited plan = every endpoint free/unlimited.
- **Docs index for agents/LLMs:** `https://docs.blitz-api.ai/llms.txt` (append `.md` to any docs URL for markdown).

## All v2 endpoints

| Category | Endpoint | What it does |
|---|---|---|
| Account | `GET /v2/account` | API-key details / health check |
| **Job Search** | **`POST /v2/jobs/search`** | **Search postings ACROSS companies** by job attributes + company firmographics |
| **Job Search** | **`POST /v2/jobs/company`** | **All postings at ONE company** from its LinkedIn URL |
| Company Search | `POST /v2/companies/search` | Search companies by industry, size, location, keywords |
| Company Enrichment | `POST /v2/companies/enrich` | Full company profile |
| Company Enrichment | `POST /v2/companies/domain-to-linkedin` | Domain → LinkedIn URL |
| Company Enrichment | `POST /v2/companies/linkedin-to-domain` | LinkedIn URL → domain |
| People Search | `POST /v2/people/find` | Find people by criteria |
| People Search | `POST /v2/people/employee-finder` | Browse all employees at one company |
| People Search | `POST /v2/people/waterfall-icp-search` | Priority-cascade best-match contact at a company |
| People Enrichment | `POST /v2/people/find-work-email` | Verified work email |
| People Enrichment | `POST /v2/people/find-phone` | Mobile & direct dial |
| People Enrichment | `POST /v2/people/reverse-email` | Email → person |
| People Enrichment | `POST /v2/people/reverse-phone` | Phone → person |
| Utilities | `POST /v2/utils/company-department-distribution` | Headcount by department (great budget/direction signal) |
| Utilities | `POST /v2/utils/company-employment-distribution` | Headcount over time |
| Utilities | `GET /v2/utils/now` | Current date/time |

> Endpoint paths for the non-job endpoints are indicative — confirm exact paths in the [interactive reference](https://docs.blitz-api.ai). The two job endpoints below are exact and tested.

---

## The two endpoints this pipeline runs on

### 1. `POST /v2/jobs/company` — every posting at one company

Use this for the account-list sweep: one call per account.

```bash
curl -s -X POST "https://api.blitz-api.ai/v2/jobs/company" \
  -H "x-api-key: $BLITZ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "company_linkedin_url": "https://www.linkedin.com/company/example-co",
    "job": {
      "date_posted": { "last_days": 90 }
    },
    "cursor": null
  }'
```

Add job-level filters when you only want signal postings (all filters AND; values inside one `include` list are OR):

```json
{
  "company_linkedin_url": "https://www.linkedin.com/company/example-co",
  "job": {
    "date_posted": { "last_days": 90 },
    "description": { "include": ["Kubernetes", "Snyk", "Databricks"] },
    "title":       { "include": ["security", "platform"], "exclude": ["intern"] }
  },
  "cursor": null
}
```

**The `description.include` filter runs server-side.** "Which of my 1,000 accounts mention tool X in a posting?" is one call per company — no downloading everything and grepping locally.

### 2. `POST /v2/jobs/search` — postings across ALL companies

Use this to *discover* accounts you don't have yet: combine job filters with company firmographics (industry, size, headcount, HQ).

```bash
curl -s -X POST "https://api.blitz-api.ai/v2/jobs/search" \
  -H "x-api-key: $BLITZ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "job": {
      "title": { "include": ["AI security", "ML platform"] },
      "date_posted": { "last_days": 30 },
      "location": { "country": ["United States"] }
    },
    "company": {
      "employee_count": { "min": 200, "max": 5000 }
    },
    "cursor": null
  }'
```

### Pagination (both endpoints)

Cursor-based. `cursor: null` = first page; each response returns a `cursor` — pass it back for the next page; `null` cursor in a response = done. Max **50 results per request**, up to **5,000 jobs per query**.

```python
cursor = None
while True:
    body["cursor"] = cursor
    r = post(url, body)
    jobs += r["jobs"]          # field name per response schema
    cursor = r.get("cursor")
    if not cursor: break
```

### What comes back per job (the fields that matter for intel)

- `job_title`, `description` (full text — this is the gold), `date_posted`
- seniority / employment type / work arrangement, location
- company block (name, LinkedIn URL, size)

Store **the complete raw object**. The decode step reads the full description; anything you throw away now you will want later.

### Gotchas (learned the hard way)

1. **Respect 5 rps.** At 1 call/company that's a 2,000-account sweep in ~7–9 minutes. Add a simple limiter; don't parallel-blast.
2. **90-day freshness gate.** Postings older than ~90 days are dead signals — always set `date_posted.last_days`. Reference them only as "the company was hiring for X," never as live intent.
3. **`include` lists are OR, filters are AND.** Two keywords in one list widens the net; two separate filters narrows it.
4. **Duplicate postings exist** (same role reposted, multi-location clones). Dedup on `(company, job_title, location)` or a description hash before decoding, or you'll pay Claude twice for the same intel.
5. **Don't decode with regex.** Titles lie ("VP" at a 10-person company, "Engineer II" owning a whole platform). The decode has to read the description with an LLM.
