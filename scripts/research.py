#!/usr/bin/env python3
"""
research.py — Supabase postings -> Claude Sonnet (decode -> brief -> score -> draft) -> account_briefs.

Reads prompts from prompts/*.md so you can tune them without touching code.
Edit prompts/03_score.md to describe YOUR product + ICP before running.

Usage:
    python scripts/research.py            # all accounts with status=pulled
    python scripts/research.py --limit 25 # pilot first!

Env: SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY
"""
import json, os, sys, time
import requests

MODEL = "claude-sonnet-5"          # bulk decode = Sonnet; swap for a bigger model on the final drafts if you like
MAX_POSTINGS_PER_ACCOUNT = 30      # cost guard for the brief step

def env(k):
    v = os.environ.get(k)
    if not v and os.path.exists(".env"):
        for line in open(".env"):
            if line.strip().startswith(f"{k}="):
                v = line.strip().split("=", 1)[1]
    if not v:
        sys.exit(f"missing env: {k}")
    return v

SB_URL, SB_KEY, ANT_KEY = env("SUPABASE_URL").rstrip("/"), env("SUPABASE_SERVICE_KEY"), env("ANTHROPIC_API_KEY")
SB_HDR = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
P = lambda name: open(os.path.join(os.path.dirname(__file__), "..", "prompts", name)).read()

def sb_get(path):
    r = requests.get(f"{SB_URL}/rest/v1/{path}", headers=SB_HDR, timeout=30); r.raise_for_status(); return r.json()

def sb_patch(table, q, patch):
    requests.patch(f"{SB_URL}/rest/v1/{table}?{q}", headers=SB_HDR, json=patch, timeout=30).raise_for_status()

def sb_upsert(table, rows, on_conflict):
    requests.post(f"{SB_URL}/rest/v1/{table}?on_conflict={on_conflict}",
                  headers={**SB_HDR, "Prefer": "resolution=merge-duplicates"}, json=rows, timeout=30).raise_for_status()

def claude(system, user, max_tokens=2000):
    """Plain Messages API call; retries on 429/529."""
    for attempt in range(5):
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=120,
                          headers={"x-api-key": ANT_KEY, "anthropic-version": "2023-06-01",
                                   "Content-Type": "application/json"},
                          json={"model": MODEL, "max_tokens": max_tokens,
                                "system": system, "messages": [{"role": "user", "content": user}]})
        if r.status_code in (429, 529):
            time.sleep(5 * (attempt + 1)); continue
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    raise RuntimeError("Claude API kept rate-limiting")

def parse_json(text):
    """Model returns JSON; tolerate code fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        t = t[4:] if t.startswith("json") else t
    return json.loads(t)

def main():
    limit = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    accounts = sb_get("accounts?status=eq.pulled&select=id,company_name&order=created_at")
    if limit: accounts = accounts[:limit]
    print(f"{len(accounts)} accounts to research (model: {MODEL})")

    decode_prompt, brief_prompt = P("01_technographic_decode.md"), P("02_intent_brief.md")
    score_prompt, outreach_prompt = P("03_score.md"), P("04_outreach.md")

    for i, a in enumerate(accounts, 1):
        posts = sb_get(f"job_postings?account_id=eq.{a['id']}&select=id,job_title,date_posted,raw,decoded"
                       f"&order=date_posted.desc&limit={MAX_POSTINGS_PER_ACCOUNT}")
        if not posts:
            sb_patch("accounts", f"id=eq.{a['id']}", {"status": "briefed"}); continue

        # --- step 1: DECODE each posting (skip ones already decoded) ---------
        for p in posts:
            if p.get("decoded"): continue
            desc = (p["raw"].get("description") or "")[:12000]
            user = f"JOB TITLE: {p['job_title']}\nDATE POSTED: {p['date_posted']}\n\nFULL POSTING TEXT:\n{desc}"
            try:
                decoded = parse_json(claude(decode_prompt, user, 1200))
            except Exception as e:
                print(f"  decode failed ({p['job_title']}): {e}"); continue
            sb_patch("job_postings", f"id=eq.{p['id']}", {"decoded": decoded, "decoded_at": "now()"})
            p["decoded"] = decoded

        # --- step 2: MAP -> one account brief --------------------------------
        digest = json.dumps([{"title": p["job_title"], "date": str(p["date_posted"]),
                              "decoded": p.get("decoded")} for p in posts], default=str)[:60000]
        brief = parse_json(claude(brief_prompt, f"COMPANY: {a['company_name']}\n\nDECODED POSTINGS:\n{digest}", 1500))

        # --- step 3: SCORE vs your ICP ---------------------------------------
        scored = parse_json(claude(score_prompt, f"ACCOUNT BRIEF:\n{json.dumps(brief)}", 800))

        # --- step 4: DRAFT movement-first outreach (only if score >= 4) ------
        draft = ""
        if int(scored.get("score", 0)) >= 4:
            draft = claude(outreach_prompt,
                           f"COMPANY: {a['company_name']}\nSTRONGEST MOVEMENT: {brief.get('strongest_movement')}\n"
                           f"BRIEF: {json.dumps(brief)}", 500)

        sb_upsert("account_briefs", [{
            "account_id": a["id"], "company_name": a["company_name"],
            "stack": brief.get("stack"), "direction": brief.get("direction"),
            "budget_signals": brief.get("budget_signals"), "hierarchy": brief.get("hierarchy"),
            "strongest_movement": brief.get("strongest_movement"),
            "icp_score": int(scored.get("score", 0)), "score_reasoning": scored.get("reasoning", ""),
            "outreach_draft": draft, "model": MODEL,
        }], "account_id")
        sb_patch("accounts", f"id=eq.{a['id']}", {"status": "briefed"})
        print(f"[{i}/{len(accounts)}] {a['company_name']}: score {scored.get('score')} — {brief.get('strongest_movement','')[:70]}")

    print("done — ranked briefs are in account_briefs. Query: order by icp_score desc.")

if __name__ == "__main__":
    main()
