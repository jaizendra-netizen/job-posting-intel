#!/usr/bin/env python3
"""
readback_count.py - prove a bulk write landed by READING it back. Never trust a write response.

Counts rows in a Supabase table through PostgREST (exact count, no rows transferred) and
exits non-zero when the count is not what you expected.

    python3 readback_count.py --table Company --expect 1250
    python3 readback_count.py --table People --schema acme --filter "loaded_at=not.is.null" --expect 980
    python3 readback_count.py --table Company --min 1000        # at least N

Env: SUPABASE_URL (https://<ref>.supabase.co) and SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY
when your schema grants anon read). Keys are read from the environment only and never printed.
"""
import argparse
import os
import sys

import requests


def main():
    ap = argparse.ArgumentParser(description="Exact row count read-back for Supabase tables.")
    ap.add_argument("--table", required=True)
    ap.add_argument("--schema", default="public", help="tenant schema (sent as Accept-Profile)")
    ap.add_argument("--filter", default="", help='PostgREST filter, e.g. "fit_verdict=eq.keep"')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--expect", type=int, help="exact count required")
    g.add_argument("--min", type=int, help="minimum count required")
    a = ap.parse_args()

    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url and os.environ.get("SUPABASE_PROJECT_REF"):
        url = f"https://{os.environ['SUPABASE_PROJECT_REF']}.supabase.co"
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    if not url or not key:
        sys.exit("missing SUPABASE_URL (or SUPABASE_PROJECT_REF) and a Supabase key in env")

    q = f"{url}/rest/v1/{a.table}?select=*"
    if a.filter:
        q += "&" + a.filter
    hdr = {"apikey": key, "Authorization": f"Bearer {key}",
           "Prefer": "count=exact", "Range": "0-0", "Accept-Profile": a.schema}
    r = requests.get(q, headers=hdr, timeout=60)
    if r.status_code not in (200, 206):
        sys.exit(f"read-back failed: HTTP {r.status_code} {r.text[:200]}")
    total = int(r.headers.get("Content-Range", "*/0").split("/")[-1] or 0)

    ok = (total == a.expect) if a.expect is not None else (total >= a.min)
    want = f"== {a.expect}" if a.expect is not None else f">= {a.min}"
    print(f"{a.schema}.{a.table} [{a.filter or 'all rows'}]: {total} rows (want {want}) -> {'OK' if ok else 'MISMATCH'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
