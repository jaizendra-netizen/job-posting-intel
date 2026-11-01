# Contact sourcing by persona (company-first, live-verified)

Use this when qualified accounts need the right person to contact. It finds people at a known
company, judges them on their real current title, verifies they still work there, and keeps
one or a few per account depending on company size.

## Contents
1. Ask for the persona
2. Pull people company-first
3. Judge titles semantically (distinct titles, not people)
4. Verify current employment
5. Junk-profile filter
6. Buyer role and how many per account
7. Resolve clean profile URLs
8. Failure modes and costs

---

## 1. Ask for the persona

Before spending anything, get from the user:
- the persona(s) in plain words (e.g. "Head of RevOps or VP Sales at the account"),
- which departments and seniorities count as **buyer** vs **champion**,
- an existing contact list to dedupe against (optional),
- how many accounts this run, and a pilot size (default 5 to 10 accounts).

Turn the persona into short LinkedIn title keywords, broad on purpose (function word plus
Director / VP / Head / Chief). Confirm them with the user.

## 2. Pull people company-first

Never resolve people name-first through Google (`site:linkedin.com/in "Name" "Company"`).
Google does not index LinkedIn profile bodies, so the company term does nothing and the search
degrades to a name-only query that returns namesakes. Providers honour a company filter; Google
does not.

Options, in the order to try:
- **Apify `harvestapi/linkedin-company-employees`**: input `companies` (company URLs),
  `jobTitles` (the persona keywords), `maxItemsPerCompany`, and `companyBatchMode: "all_at_once"`
  so many companies share one actor start. Build the input in Python or post it from a file:
  the mode label contains a `$` that the shell will expand.
- **Prospeo `/search-person`** with the company domain plus a job-title filter, or **Blitz**
  people search / employee finder on the company.
- For very large companies (roughly 10k+ employees), keyword employee search returns a ranked
  sample, not a roster. Use a title-indexed database search to get profile URL pointers, then
  live-scrape each pointer before you trust it.

## 3. Judge titles semantically

- Read the current title from the position field (`currentPositions[0].title` or
  `currentPosition[0].position` depending on the actor), **not** `headline`, which is marketing copy
  and is often blank in short scrape modes.
- Grade **distinct titles**, not people: dedupe titles, have one sub-agent grade a batch of about
  100 titles into Grade 1 / 2 / 3 / Drop with a short reason, then join back. Far cheaper than
  grading every person.
- Grid: department x seniority (CXO / VP-Head-Director / Manager-Lead / IC). Make sure every
  department you care about has a Grade 1 path, or a whole persona disappears.
- Ambiguous titles ("Director", "Managing Director", "President" with no function word): scrape
  that one profile in full mode and judge from the about section and experience.
- Never regex the grade. "VP Sales Operations" is sales, not operations; "Product Owner" is not a
  company owner. Those are exactly the cases pattern matching gets wrong.

## 4. Verify current employment

Databases are stale. Before a contact is used, confirm the person currently works at the target
company: live profile scrape (Apify `harvestapi/linkedin-profile-scraper`, mode
`"Profile details no email ($4 per 1k)"`, field `queries`) or a live enrichment call (Trigify
`/v1/profile/enrich`). Compare the current company to the account.

- Different company now: drop, unless they left within the current year and your campaign
  benefits from people who know the account (then keep them flagged "recently departed" so the
  message acknowledges the move).
- The verification gate tests for **contradiction, not plausibility**: a rare surname with a
  senior title is not a verified identity if the employer does not match.

## 5. Junk-profile filter

Company pages attract fake and spam profiles that list the company as employer. Drop a profile
when it is blank (no headline and no about), the name carries digits, underscores or gaming
handles, the name is a single token or a repeated token, the "person" is actually the page
(shares the company acronym), or the title says retired / former. Zero real contacts at a heavily
spammed company is a correct result.

## 6. Buyer role and how many per account

Tag each kept person: **Economic buyer** (can sign), **Champion** (owns the pain, can introduce),
**Influencer** (senior, neither). Lead with the economic buyer, keep the champion as the second door.

Scale by headcount, because who the buyer is shifts with size:
- under ~100 employees: keep 1 (the founder / CEO / owner usually is the buyer),
- ~100 to 500: keep 2 (top executive plus the function leader),
- 500+: keep 2 to 3 function leaders (the CEO is too far from the decision).

Record `why_qualified` on every kept contact: the title text and the reason.

## 7. Resolve clean profile URLs

Short-mode employee scrapes may return member-ID URLs (`/in/ACwAA...`). Senders and CRMs can
reject them. Run the kept people through the profile scraper and take `publicIdentifier`.
**Map results back by name (and input URL), never by position**: the scraper reorders its output.
Join everything on the `/in/<slug>` segment (`scripts/normalize.py`), URL-decoded, never on the
full URL string.

## 8. Failure modes and costs

| Symptom | Cause | Fix |
|---|---|---|
| Wrong people with the right name | Name-first Google search | Company-first pull, then match inside the company pool |
| Titles read like slogans | Used `headline` | Use the current-position title field |
| Every contact has someone else's URL | Mapped scraper output by order | Map by name + input URL, assert name equality |
| ~15% of paid scrapes do not join | Matched full URL strings (country subdomains) | Join on URL-decoded `/in/<slug>` |
| Profile-search returns everyone, ignoring titles | Wrong input field | Check the actor's input schema; use the exact-title array filter it documents |
| Actor bill much higher than expected | One run per company or per person | Batch companies into one run; some search actors charge per run |
| Some member-ID URLs 404 | Stale or restricted IDs from a search index | Treat as unreachable; they cannot be messaged either |

Pricing changes; read the current price on each actor's Apify page and your plan before a run.
The actor mode labels quoted above (for example "$4 per 1k") are list prices shown in the actor
input, and actor runs can also carry a per-start fee. Always run a pilot of 5 to 10 accounts and
show the user the real spend and a sample before scaling.
