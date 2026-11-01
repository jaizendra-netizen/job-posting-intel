#!/usr/bin/env python3
"""
normalize.py - mechanical identity keys (no judgment, so plain string rules are fine).

    from normalize import normalize_domain, linkedin_slug, company_slug

normalize_domain("https://www.Acme.com/about")  -> "acme.com"
linkedin_slug("https://uk.linkedin.com/in/Jane-Doe-123/?x=1") -> "jane-doe-123"
company_slug("https://www.linkedin.com/company/acme-inc/about") -> "acme-inc"

Why slugs: stored LinkedIn URLs carry country subdomains (uk., ch., ...), trailing
paths and query strings, and percent-encoded characters. Matching full URL strings
silently loses rows you already paid to scrape. Always join on the slug.

CLI:  python3 normalize.py domain <value> | person <url> | company <url>
"""
import sys
from urllib.parse import urlparse, unquote

# Hosts that are never a company's own domain (link-in-bio, social, shorteners).
SHARED_HOSTS = {
    "linktr.ee", "linkedin.com", "bit.ly", "youtube.com", "calendly.com",
    "twitter.com", "x.com", "instagram.com", "facebook.com", "medium.com",
    "substack.com", "beacons.ai", "notion.site", "gmail.com", "outlook.com",
}
# Subdomains that point at a section of a company site, not a different company.
SECTION_SUBDOMAINS = ("www.", "careers.", "jobs.", "about.", "go.", "info.")


def normalize_domain(raw):
    """lowercase, strip scheme / www / section subdomain / path / port -> host, or None."""
    if not raw:
        return None
    raw = str(raw).strip().lower()
    if not raw:
        return None
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    host = (parsed.netloc or parsed.path).split("/")[0].split("@")[-1].split(":")[0]
    for sub in SECTION_SUBDOMAINS:
        if host.startswith(sub):
            host = host[len(sub):]
            break
    if "." not in host:
        return None
    if any(host == h or host.endswith("." + h) for h in SHARED_HOSTS):
        return None
    return host


def _segment_after(url, marker):
    if not url:
        return None
    u = unquote(str(url)).strip()
    low = u.lower()
    i = low.find(marker)
    if i < 0:
        return None
    rest = u[i + len(marker):]
    slug = rest.split("/")[0].split("?")[0].split("#")[0].strip()
    return slug.lower() or None


def linkedin_slug(url):
    """Person profile: the /in/<slug> segment, lowercased and URL-decoded."""
    return _segment_after(url, "/in/")


def company_slug(url):
    """Company page: the /company/<slug> segment. Returns None for search-result URLs."""
    if url and "/search/" in str(url):
        return None  # provider fallback like /search/results/?keywords=X is not a company page
    return _segment_after(url, "/company/")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: normalize.py domain|person|company <value>")
    kind, val = sys.argv[1], sys.argv[2]
    fn = {"domain": normalize_domain, "person": linkedin_slug, "company": company_slug}.get(kind)
    if not fn:
        sys.exit("kind must be domain, person or company")
    print(fn(val))
