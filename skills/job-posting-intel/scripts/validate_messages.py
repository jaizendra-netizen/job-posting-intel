#!/usr/bin/env python3
"""
validate_messages.py - mechanical pre-send validator for outreach copy.

This is the code half of message QA: it checks things that are true or false on the
string itself (braces, placeholders, dashes, length, links, greeting name). It does NOT
judge relevance or tone; that is the independent LLM judge's job. Any failure means:
do not ship this row as written - fix it or fall back to the approved generic message.

Input: JSONL, one lead per line. Each line needs the name field and one or more message
fields you list with --fields.

    python3 validate_messages.py --in drafts.jsonl --fields li_m1,li_m2,email_body_1 \
        --name-field first_name --max-words 100 --max-questions 1 --out report.jsonl

    # LinkedIn connection notes: 300 chars, no links
    python3 validate_messages.py --in notes.jsonl --fields note --max-chars 300 --no-links

Exit code 0 = every row passed, 1 = at least one failure (report lists them).
"""
import argparse
import json
import re
import sys
import unicodedata

PLACEHOLDER_PATTERNS = [
    r"\{[^}]*\}",              # any brace token: {first_name}, {{x}}, spintax {a|b}
    r"\[[A-Z][A-Za-z _]+\]",   # [FirstName], [SIGNAL], [Company]
    r"<[A-Z_ ]{3,}>",          # <YOUR_PRODUCT>
    r"\bcoalesce\(",           # SQL merge debris
    r"\|\|",
    r"\bnull\b|\bundefined\b|\bNaN\b",
]
DASHES = ["\u2014", "\u2013"]  # em dash, en dash
LINK_RE = re.compile(r"(https?://|www\.)|\b[a-z0-9-]+\.(com|io|ai|dev|co|net|org)\b", re.I)
DEFAULT_BANNED = [
    "circling back", "following up", "just checking in", "close the loop",
    "no pitch", "no strings", "no pressure", "i hope this finds you well",
    "quick context on me", "a bit about me", "let me introduce myself",
    "i saw you liked", "i saw you commented", "you viewed my profile", "visited our site",
    "glad we are already connected", "great to be connected", "since we are connected",
]


def ascii_name(name):
    """María -> Maria (transliterate, never drop the letter)."""
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()


def clean_first_name(raw):
    """'Dr. Matt Lee, CISSP' -> 'Matt'. Drops honorifics, credentials, emoji."""
    if not raw:
        return ""
    s = str(raw).split(",")[0]
    s = re.sub(r"^(dr|mr|mrs|ms|prof)\.?\s+", "", s.strip(), flags=re.I)
    s = "".join(ch for ch in s if ch.isalpha() or ch in " -'")
    return s.split()[0] if s.split() else ""


def check(text, name, a, banned):
    errs = []
    if not text or not str(text).strip():
        return ["empty message"]
    t = str(text)
    for pat in PLACEHOLDER_PATTERNS:
        m = re.search(pat, t)
        if m:
            errs.append(f"placeholder/debris: {m.group(0)!r}")
    for d in DASHES:
        if d in t:
            errs.append("contains em/en dash")
            break
    words = len(t.split())
    if a.max_words and words > a.max_words:
        errs.append(f"{words} words > {a.max_words}")
    if a.max_chars and len(t) > a.max_chars:
        errs.append(f"{len(t)} chars > {a.max_chars}")
    q = t.count("?")
    if a.max_questions is not None and q > a.max_questions:
        errs.append(f"{q} questions > {a.max_questions}")
    if a.no_links and LINK_RE.search(t):
        errs.append("contains a link or bare domain")
    low = t.lower()
    for b in banned:
        if b in low:
            errs.append(f"banned phrase: {b!r}")
    if name:
        first = ascii_name(clean_first_name(name))
        greet = re.match(r"\s*(hi|hey|hello)\s+([A-Za-z'-]+)", t, flags=re.I)
        if greet and first and greet.group(2).lower() != first.lower():
            errs.append(f"greeting name {greet.group(2)!r} != row name {first!r}")
    if any(ord(ch) > 0x2600 for ch in t[:40]):
        errs.append("emoji/symbol in opening")
    return errs


def main():
    ap = argparse.ArgumentParser(description="Mechanical outreach copy validator.")
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--fields", required=True, help="comma-separated message fields")
    ap.add_argument("--name-field", default="first_name")
    ap.add_argument("--max-words", type=int, default=0)
    ap.add_argument("--max-chars", type=int, default=0)
    ap.add_argument("--max-questions", type=int, default=None)
    ap.add_argument("--no-links", action="store_true")
    ap.add_argument("--banned-file", help="extra banned phrases, one per line")
    ap.add_argument("--out", help="write per-row report JSONL here")
    a = ap.parse_args()

    banned = list(DEFAULT_BANNED)
    if a.banned_file:
        banned += [l.strip().lower() for l in open(a.banned_file) if l.strip()]
    fields = [f.strip() for f in a.fields.split(",") if f.strip()]

    rows = fails = 0
    out = open(a.out, "w") if a.out else None
    for line in open(a.infile):
        if not line.strip():
            continue
        rows += 1
        rec = json.loads(line)
        problems = {}
        for f in fields:
            e = check(rec.get(f), rec.get(a.name_field), a, banned)
            if e:
                problems[f] = e
        if problems:
            fails += 1
        if out:
            out.write(json.dumps({"row": rows, "id": rec.get("id") or rec.get("linkedin_url"),
                                  "pass": not problems, "problems": problems}) + "\n")
        elif problems:
            print(f"row {rows}: {problems}")
    print(f"{rows} rows checked, {fails} failed, {rows - fails} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
