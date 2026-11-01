#!/usr/bin/env python3
"""
discover_accounts.py - find accounts you do NOT have yet from live job postings.

Calls Blitz POST /v2/jobs/search (postings across all companies, filtered by job attributes and
company firmographics), collapses results to one row per company, and writes an accounts CSV in
the exact shape scripts/pull_jobs.py expects: company_name,company_linkedin_url.

    python3 discover_accounts.py --title "platform engineer" --title "ML platform" \
        --last-days 30 --country "United States" --min-emp 200 --max-emp 5000 \
        --max-jobs 500 --out data/discovered_accounts.csv

Each returned job costs Blitz credits on a credit plan (1 credit per job on the trial), so
--max-jobs is a hard ceiling. Start small and show the user the count before a bigger pull.

Env: BLITZ_API_KEY (read from env or ./.env; never printed).
"""
import argparse
import csv
import json
import os
import sys
import time

import requests

BLITZ = "https://api.blitz-api.ai"


def env(k):
    v = os.environ.get(k)
    if not v and os.path.exists(".env"):
        for line in open(".env"):
            if line.strip().startswith(f"{k}="):
                v = line.strip().split("=", 1)[1]
    if not v:
        sys.exit(f"missing env: {k}")
    return v


def main():
    ap = argparse.ArgumentParser(description="Blitz job search -> new accounts CSV")
    ap.add_argument("--title", action="append", default=[], help="job title include term (OR)")
    ap.add_argument("--description", action="append", default=[], help="description include term (OR)")
    ap.add_argument("--exclude-title", action="append", default=[])
    ap.add_argument("--last-days", type=int, default=30)
    ap.add_argument("--country", action="append", default=[])
    ap.add_argument("--min-emp", type=int)
    ap.add_argument("--max-emp", type=int)
    ap.add_argument("--max-jobs", type=int, default=200, help="hard ceiling on jobs fetched")
    ap.add_argument("--known", help="existing accounts CSV to exclude (company_linkedin_url column)")
    ap.add_argument("--raw-out", default="data/discovery_raw.jsonl", help="complete job objects")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if not a.title and not a.description:
        sys.exit("give at least one --title or --description term")

    key = env("BLITZ_API_KEY")
    job = {"date_posted": {"last_days": a.last_days}}
    if a.title or a.exclude_title:
        job["title"] = {k: v for k, v in (("include", a.title), ("exclude", a.exclude_title)) if v}
    if a.description:
        job["description"] = {"include": a.description}
    if a.country:
        job["location"] = {"country": a.country}
    body = {"job": job, "cursor": None}
    if a.min_emp or a.max_emp:
        rng = {}
        if a.min_emp:
            rng["min"] = a.min_emp
        if a.max_emp:
            rng["max"] = a.max_emp
        body["company"] = {"employee_count": rng}

    known = set()
    if a.known and os.path.exists(a.known):
        known = {r.get("company_linkedin_url", "").strip().rstrip("/").lower()
                 for r in csv.DictReader(open(a.known))}

    os.makedirs(os.path.dirname(a.raw_out) or ".", exist_ok=True)
    raw = open(a.raw_out, "a")
    companies, fetched = {}, 0
    while fetched < a.max_jobs:
        r = requests.post(f"{BLITZ}/v2/jobs/search", json=body, timeout=60,
                          headers={"x-api-key": key, "Content-Type": "application/json"})
        if r.status_code == 429:
            time.sleep(2)
            continue
        r.raise_for_status()
        data = r.json()
        page = data.get("jobs") or data.get("results") or []
        for j in page:
            raw.write(json.dumps(j) + "\n")
            co = j.get("company") or {}
            url = (co.get("linkedin_url") or co.get("company_linkedin_url") or "").strip()
            name = (co.get("name") or j.get("company_name") or "").strip()
            if not url:
                continue
            k = url.rstrip("/").lower()
            if k in known:
                continue
            c = companies.setdefault(k, {"company_name": name, "company_linkedin_url": url, "jobs": 0})
            c["jobs"] += 1
        fetched += len(page)
        body["cursor"] = data.get("cursor")
        time.sleep(0.25)  # stay under 5 requests per second
        if not body["cursor"] or not page:
            break
    raw.close()

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["company_name", "company_linkedin_url", "matching_jobs"])
        w.writeheader()
        for c in sorted(companies.values(), key=lambda x: -x["jobs"]):
            w.writerow({"company_name": c["company_name"],
                        "company_linkedin_url": c["company_linkedin_url"],
                        "matching_jobs": c["jobs"]})
    print(f"{fetched} jobs fetched, {len(companies)} new companies -> {a.out} (raw: {a.raw_out})")
    print("If company fields are empty, inspect one raw line: the response field names may differ.")


if __name__ == "__main__":
    main()
