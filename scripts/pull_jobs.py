#!/usr/bin/env python3
"""
pull_jobs.py — account list CSV -> Blitz /v2/jobs/company -> Supabase (raw-first).

Usage:
    python scripts/pull_jobs.py accounts.csv
CSV columns: company_name,company_linkedin_url

Env (.env or exported): BLITZ_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import csv, hashlib, json, os, sys, time
import requests

# ---- config -----------------------------------------------------------------
BLITZ = "https://api.blitz-api.ai"
LAST_DAYS = 90            # dead-signal gate: postings older than this are stale intent
RATE_SLEEP = 0.25         # ~4 rps, safely under Blitz's 5 rps/endpoint

def env(k):
    v = os.environ.get(k)
    if not v and os.path.exists(".env"):
        for line in open(".env"):
            if line.strip().startswith(f"{k}="):
                v = line.strip().split("=", 1)[1]
    if not v:
        sys.exit(f"missing env: {k}")
    return v

BLITZ_KEY, SB_URL, SB_KEY = env("BLITZ_API_KEY"), env("SUPABASE_URL").rstrip("/"), env("SUPABASE_SERVICE_KEY")
SB_HDR = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}

# ---- supabase helpers (plain PostgREST, no SDK needed) ----------------------
def sb_upsert(table, rows, on_conflict):
    r = requests.post(f"{SB_URL}/rest/v1/{table}?on_conflict={on_conflict}",
                      headers={**SB_HDR, "Prefer": "resolution=merge-duplicates,return=representation"},
                      json=rows, timeout=30)
    r.raise_for_status()
    return r.json()

def sb_patch(table, match, patch):
    q = "&".join(f"{k}=eq.{v}" for k, v in match.items())
    requests.patch(f"{SB_URL}/rest/v1/{table}?{q}", headers=SB_HDR, json=patch, timeout=30).raise_for_status()

# ---- blitz ------------------------------------------------------------------
def pull_company_jobs(linkedin_url):
    """All postings at one company, last LAST_DAYS days, cursor-paginated."""
    jobs, cursor = [], None
    while True:
        body = {"company_linkedin_url": linkedin_url,
                "job": {"date_posted": {"last_days": LAST_DAYS}},
                "cursor": cursor}
        r = requests.post(f"{BLITZ}/v2/jobs/company", timeout=60,
                          headers={"x-api-key": BLITZ_KEY, "Content-Type": "application/json"},
                          json=body)
        if r.status_code == 429:          # backoff on rate limit
            time.sleep(2); continue
        r.raise_for_status()
        data = r.json()
        page = data.get("jobs") or data.get("results") or []
        jobs.extend(page)
        cursor = data.get("cursor")
        time.sleep(RATE_SLEEP)
        if not cursor or not page:
            return jobs

def posting_key(j):
    """Stable dedup key: Blitz id if present, else hash of title+location+date."""
    if j.get("id"):
        return str(j["id"])
    basis = f'{j.get("job_title","")}|{json.dumps(j.get("location",""),sort_keys=True)}|{j.get("date_posted","")}'
    return hashlib.sha256(basis.encode()).hexdigest()[:24]

# ---- main -------------------------------------------------------------------
def main(csv_path):
    rows = list(csv.DictReader(open(csv_path)))
    print(f"{len(rows)} accounts")
    for i, row in enumerate(rows, 1):
        name, url = row["company_name"].strip(), row["company_linkedin_url"].strip()
        acct = sb_upsert("accounts", [{"company_name": name, "linkedin_url": url}], "linkedin_url")[0]
        try:
            jobs = pull_company_jobs(url)
        except Exception as e:
            print(f"[{i}] {name}: ERROR {e}")
            sb_patch("accounts", {"id": acct["id"]}, {"status": "error"})
            continue
        # dedup within the pull, then store RAW-FIRST
        seen, payload = set(), []
        for j in jobs:
            k = posting_key(j)
            if k in seen: continue
            seen.add(k)
            payload.append({"account_id": acct["id"], "posting_key": k,
                            "job_title": j.get("job_title"), "date_posted": j.get("date_posted"),
                            "posting_url": j.get("url") or j.get("job_url"),
                            "raw": j})                       # <- the COMPLETE object
        for b in range(0, len(payload), 200):
            sb_upsert("job_postings", payload[b:b+200], "account_id,posting_key")
        sb_patch("accounts", {"id": acct["id"]}, {"status": "pulled", "posting_count": len(payload)})
        print(f"[{i}/{len(rows)}] {name}: {len(payload)} postings")
    print("done — raw postings are in Supabase. Next: python scripts/research.py")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/pull_jobs.py accounts.csv")
    main(sys.argv[1])
