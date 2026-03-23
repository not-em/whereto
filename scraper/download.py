"""
download.py — Phase 1: Fetch & cache raw HTML for all visa requirement pages.

Run this ONCE. It will:
  1. Use the Wikipedia API to get all page titles in the category (handles pagination)
  2. Fetch each page's HTML and save to cache/
  3. Skip pages already cached — safe to re-run if interrupted

Usage:
    python download.py

Output:
    cache/<slug>.html  — one file per nationality page
    cache/_index.json  — list of all {title, slug, url} for the parser to use
"""

import json
import os
import time
import urllib.request
import urllib.parse
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

CATEGORY = "Category:Visa_requirements_by_nationality"
API_BASE = "https://en.wikipedia.org/w/api.php"
WIKI_BASE = "https://en.wikipedia.org/wiki/"

# Be polite — wait between requests
DELAY_SECONDS = 0.5

HEADERS = {
    "User-Agent": "VisaMapper/1.0 (educational project; contact via github)"
}


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def get_category_members() -> list[dict]:
    """Fetch all page titles in the category, handling API pagination."""
    members = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": CATEGORY,
        "cmlimit": "500",
        "cmnamespace": "0",  # main articles only
        "format": "json",
    }
    page_num = 1

    while True:
        url = API_BASE + "?" + urllib.parse.urlencode(params)
        print(f"  Fetching category page {page_num}...")
        raw = fetch_url(url)
        data = json.loads(raw)

        batch = data["query"]["categorymembers"]
        members.extend(batch)
        print(f"  Got {len(batch)} titles (total so far: {len(members)})")

        # Check for continuation
        if "continue" not in data:
            break
        params["cmcontinue"] = data["continue"]["cmcontinue"]
        page_num += 1
        time.sleep(DELAY_SECONDS)

    return members


def title_to_slug(title: str) -> str:
    """Convert a Wikipedia title to a safe filename slug."""
    return title.replace(" ", "_").replace("/", "-")


def download_page(title: str, slug: str) -> bool:
    """Download a single page and save to cache. Returns True if downloaded, False if skipped."""
    cache_path = CACHE_DIR / f"{slug}.html"

    if cache_path.exists():
        print(f"  [SKIP] {title}")
        return False

    url = WIKI_BASE + urllib.parse.quote(title.replace(" ", "_"))
    try:
        html = fetch_url(url)
        cache_path.write_text(html, encoding="utf-8")
        print(f"  [SAVE] {title}")
        return True
    except Exception as e:
        print(f"  [ERROR] {title}: {e}")
        return False


def main():
    print("=" * 60)
    print("PHASE 1: Downloading Wikipedia visa requirement pages")
    print("=" * 60)

    # Step 1: Get all category members
    print("\nFetching category index from Wikipedia API...")
    members = get_category_members()
    print(f"\nFound {len(members)} pages total.")

    # Filter to only visa requirement pages (exclude any stray category members)
    visa_pages = [
        m for m in members
        if "Visa requirements for" in m["title"]
    ]
    print(f"Filtered to {len(visa_pages)} visa requirement pages.")

    # Build index
    index = []
    for m in visa_pages:
        title = m["title"]
        slug = title_to_slug(title)
        url = WIKI_BASE + urllib.parse.quote(title.replace(" ", "_"))
        index.append({"title": title, "slug": slug, "url": url})

    # Save index
    index_path = CACHE_DIR / "_index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\nIndex saved to {index_path}")

    # Step 2: Download each page
    print(f"\nDownloading {len(index)} pages to {CACHE_DIR}/ ...")
    print("(Already-cached pages will be skipped — safe to re-run)\n")

    downloaded = 0
    skipped = 0
    errors = 0

    for i, entry in enumerate(index, 1):
        print(f"[{i:03d}/{len(index)}] ", end="")
        result = download_page(entry["title"], entry["slug"])
        if result:
            downloaded += 1
            time.sleep(DELAY_SECONDS)  # only delay on actual downloads
        else:
            skipped += 1

    print("\n" + "=" * 60)
    print(f"Done! Downloaded: {downloaded}, Skipped: {skipped}, Errors: {errors}")
    print(f"Cache directory: {CACHE_DIR.resolve()}")
    print("Now run: python parse.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
