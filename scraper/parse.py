"""
parse.py — Phase 2: Parse cached HTML into clean visa_data.json.

Run this as many times as you like — reads only from cache/, no network calls.
Tweak the normalisation logic below and re-run instantly.

Usage:
    python parse.py

Output:
    visa_data.json
"""

import json
import re
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("Please install beautifulsoup4: pip install beautifulsoup4")

CACHE_DIR = Path(__file__).parent / "cache"
OUTPUT_FILE = Path(__file__).parent.parent / "visa_data.json"

# ---------------------------------------------------------------------------
# COUNTRY NAME NORMALISATION
# Wikipedia uses inconsistent names across pages — standardise here
# ---------------------------------------------------------------------------

COUNTRY_ALIASES = {
    "Ivory Coast":                      "Côte d'Ivoire",
    "Czechia":                          "Czech Republic",
    "The Bahamas":                      "Bahamas",
    "The Gambia":                       "Gambia",
    "Republic of the Congo":            "Congo",
    "Democratic Republic of the Congo": "DR Congo",
    "Federated States of Micronesia":   "Micronesia",
    "Myanmar (Burma)":                  "Myanmar",
    "East Timor":                       "Timor-Leste",
    "Vatican":                          "Vatican City",
    "Holy See":                         "Vatican City",
    "St. Kitts and Nevis":              "Saint Kitts and Nevis",
    "St. Lucia":                        "Saint Lucia",
    "St. Vincent and the Grenadines":   "Saint Vincent and the Grenadines",
    "Sao Tome and Principe":            "São Tomé and Príncipe",
    "Republic of Ireland":              "Ireland",
    "South Korea":                      "South Korea",
    "North Korea":                      "North Korea",
}

def normalise_country(name: str) -> str:
    return COUNTRY_ALIASES.get(name, name)


# ---------------------------------------------------------------------------
# FOOTNOTE / CITATION STRIPPING
# ---------------------------------------------------------------------------

def strip_footnotes(text: str) -> str:
    """Remove Wikipedia citation markers like [1], [233], [note 1] etc."""
    text = re.sub(r'\[\s*(?:note\s*)?\w{1,6}\s*\]', '', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


def clean_cell(cell) -> str:
    """Extract clean text from a BeautifulSoup cell, stripping footnotes."""
    for sup in cell.find_all('sup'):
        sup.decompose()
    text = cell.get_text(separator=' ', strip=True)
    return strip_footnotes(text)


# ---------------------------------------------------------------------------
# VISA STATUS NORMALISATION
# ---------------------------------------------------------------------------

STATUS_PRIORITY = {
    "visa_free":            0,
    "eta":                  1,
    "evisa":                2,
    "visa_on_arrival":      3,
    "evisa_or_voa":         3,
    "visa_required":        4,
    "admission_refused":    5,
    "unknown":              6,
}

STATUS_COLOURS = {
    "visa_free":            "#2ecc71",
    "eta":                  "#3498db",
    "evisa":                "#9b59b6",
    "visa_on_arrival":      "#f39c12",
    "evisa_or_voa":         "#e67e22",
    "visa_required":        "#e74c3c",
    "admission_refused":    "#1a252f",
    "unknown":              "#bdc3c7",
}

def normalise_status(raw: str) -> str:
    r = raw.lower().strip()

    # Strip dates and bare years — these are parser noise
    r = re.sub(r'\d{1,2}\s+\w+\s+\d{4}', '', r).strip()
    r = re.sub(r'^\d{4}$', '', r).strip()

    if not r or r in ('n/a', '—', '—n/a'):
        return "unknown"
    
    # "Indefinite" typically means special status (e.g., Compact of Free Association)
    if r == "indefinite":
        return "visa_free"

    # ---- Banned / refused / restricted -----------------------------------
    if any(x in r for x in [
        "admission refused", "admission restricted",
        "not admitted", "entry refused",
        "visa restricted", "visa issuance ban", "visa issuance suspended",
        "travel prohibited", "travel banned", "travel illegal",
        "travel restricted",
        "passport not recognized", "passport not recognised",
        "restricted visa required", "partial visa restrictions",
        "de facto visa required", "de facto visa",
        "visa de facto required",
        "affidavit of identity required",
        "invitation required",
    ]):
        return "admission_refused"

    # ---- Freedom of movement / visa free ---------------------------------
    if any(x in r for x in [
        "freedom of movement",
        "right of abode",
        "home return permit",
        "id card valid",
    ]):
        return "visa_free"

    # ---- Visa free variants ----------------------------------------------
    if any(x in r for x in [
        "visa not required",
        "visa free",
        "visa-free",
        "no visa required",
        "free visa on arrival",
        "free visitor",
        "free entry permit",
        "free evisa",
        "free eta",
        "entry permit on arrival",
        "permit on arrival",
        "visitor's permit on arrival",
        "visitor permit on arrival",
        "easy visitor permit",
        "ease",
        "trans-tasman",
        "particular visit regime",
        "pre-enrolment",
    ]):
        if "visa required" in r and "not required" not in r:
            pass  # fall through — "visa required" wins
        else:
            return "visa_free"

    # ---- ETA / lightweight electronic pre-auth ---------------------------
    if any(x in r for x in [
        "eta required",
        "electronic travel auth",
        "electronic travel authoris",
        "electronic travel authoriz",
        "electronic authorization",
        "eta-il", "eta il",
        "k-eta", "korean electronic travel",
        "nzeta", "new zealand electronic travel",
        "evisitor",
        "electronic border",
        "electronic authorization system",
        "esta",
        "visa waiver program",
        "electronic visa waiver",
        "ave",
        "eta uk",
        "bespoke uk immigration",
        " eta",
        "eta/",
        "/eta",
        "evisitor or electronic",
    ]):
        return "eta"
    
    # Standalone "eta" - must come after other checks to avoid false positives
    if r == "eta":
        return "eta"

    # ---- eVisa OR Visa on arrival — combined -----------------------------
    if (("evisa" in r or "e-visa" in r or "e visa" in r
         or "online visa" in r or "electronic visa" in r
         or "e-voa" in r or "evoa" in r)
            and ("on arrival" in r or "voa" in r)):
        return "evisa_or_voa"

    if "on arrival" in r and ("evisa" in r or "e-visa" in r or "online visa" in r):
        return "evisa_or_voa"

    if "tourist card" in r and ("evisa" in r or "on arrival" in r):
        return "evisa_or_voa"

    # ---- Pure eVisa ------------------------------------------------------
    if any(x in r for x in [
        "evisa", "e-visa", "e visa",
        "electronic visa",
        "online visa",
        "e-voa",
        "evoa",
        "pre-visa on arrival",
        "pre-approved visa on arrival",
        "online visitor",
        "visitor e600",
    ]):
        return "evisa"

    # ---- Visa on arrival -------------------------------------------------
    if any(x in r for x in [
        "on arrival",
        "visa on arrival",
        "tourist card required",
        "tourist card",
    ]):
        return "visa_on_arrival"

    # ---- Visa required ---------------------------------------------------
    if any(x in r for x in [
        "visa required",
        "visa is required",
        "requires a visa",
        "online visa required",
        "permission required",
        "special permit",
    ]):
        return "visa_required"

    if "visa" in r:
        return "visa_required"

    return "unknown"


# ---------------------------------------------------------------------------
# PAGE PARSING
# ---------------------------------------------------------------------------

def extract_nationality(title: str) -> str:
    # Handle special Chinese variants explicitly
    if "Hong Kong" in title:
        return "Chinese (Hong Kong)"
    if "Macau" in title:
        return "Chinese (Macau)"
    if "Chinese citizens" in title and "Hong Kong" not in title and "Macau" not in title:
        return "Chinese"
    
    # Handle British variants
    if "British Nationals (Overseas)" in title:
        return "British Nationals (Overseas)"
    if "British Overseas Territories" in title:
        return "British Overseas Territories"
    if "British Overseas citizens" in title:
        return "British Overseas"
    
    # Standard extraction patterns
    m = re.match(r"Visa requirements for (.+?) citizens?", title, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.match(r"Visa requirements for citizens of (.+)", title, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return title


def is_main_table(rows: list) -> bool:
    if len(rows) < 3:  # Reduced from 5 to handle smaller tables
        return False
    
    # Check header row
    header_cells = rows[0].find_all(['th', 'td'])
    if header_cells:
        header_text = ' '.join(c.get_text(strip=True).lower() for c in header_cells)
        
        # Reject statistics/informational tables and health/vaccination tables
        if any(keyword in header_text for keyword in [
            'number of visitors', 'visitors', 'arrivals',
            'lost or stolen', 'passport', 'passports',
            'statistics', 'data', 'year',
            'vaccination', 'yellow fever', 'health', 'disease', 'malaria',
        ]):
            return False
        
        # Match both singular and plural forms
        if 'country' in header_text or 'countries' in header_text or 'region' in header_text:
            return True
    
    # For tables without proper headers, check if first data rows contain country links
    # Check both td and th cells since special territories tables use th tags
    for row in rows[:min(3, len(rows))]:
        cells = row.find_all('td')
        if cells:
            # Look for country/region links in first cell
            link = cells[0].find('a')
            if link and link.get('title'):
                # Many country pages have titles
                return True
        
        # Also check th cells for special territories
        th_cells = row.find_all('th')
        if th_cells and not th_cells[0].get('colspan'):
            link = th_cells[0].find('a')
            if link and link.get('title'):
                return True
    
    return False


def parse_page(html: str, source_url: str) -> dict:
    """
    Parse a single cached HTML page.
    Returns {country: {status, label, stay, notes, color, priority}}
    plus _source_url at the top level.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = {}

    # Try standard wikitable first
    tables = soup.find_all("table", class_="wikitable")
    
    # If no wikitable found, try any table with sortable class or any table at all
    if not tables:
        tables = soup.find_all("table", class_="sortable")
    if not tables:
        # For simple pages like Abkhazian, look for any table before the first h2
        all_tables = soup.find_all("table")
        for table in all_tables:
            # Skip navigation boxes and other metadata tables
            if "navbox" in table.get("class", []) or "nowraplinks" in table.get("class", []):
                continue
            if "mw-collapsible" in table.get("class", []):
                continue
            # Check if it contains country links
            if table.find("a", title=lambda t: t and "Visa policy" not in t):
                tables = [table]
                break

    for table in tables:
        # Skip collapsed tables (usually historical/special cases, not current requirements)
        if "collapsed" in table.get("class", []):
            continue
        if "mw-collapsible" in table.get("class", []) and "autocollapse" in table.get("class", []):
            continue
            
        rows = table.find_all("tr")
        if not is_main_table(rows):
            continue

        # Detect column count from first real data row
        num_cols = 2
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2 and not cells[0].get('colspan'):
                num_cols = len(cells)
                break

        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 1:
                continue
            if cells[0].get('colspan'):
                continue  # section header row

            country = clean_cell(cells[0])
            
            # Skip rowspan continuation rows (where first cell has rowspan, later rows are empty)
            if cells[0].get('rowspan'):
                # This is the start of a rowspan block - extract country normally
                pass
            elif not country or not cells[0].find('a'):
                # No country name and no link = continuation of previous rowspan
                continue
            
            # Handle single-column tables (country list only = visa free)
            if len(cells) == 1:
                visa_raw = "Visa not required"
                stay = ""
                notes = ""
            else:
                if len(cells) < 2:
                    continue
                visa_raw = clean_cell(cells[1])
                stay = clean_cell(cells[2]) if num_cols > 2 and len(cells) > 2 else ""
                notes = clean_cell(cells[3]) if num_cols > 3 and len(cells) > 3 else ""

            if not country or not visa_raw:
                continue
            if country.lower() in ("country", "region", "country / region", "country/region"):
                continue
            if len(country) > 80:
                continue

            # Normalise country name
            country = normalise_country(country)

            # If notes column empty, try splitting label on semicolon
            label = visa_raw
            if not notes and len(visa_raw) > 40:
                parts = re.split(r'\s*;\s*', visa_raw, maxsplit=1)
                if len(parts) == 2 and len(parts[0]) < 60:
                    label = parts[0].strip()
                    notes = parts[1].strip()

            status = normalise_status(visa_raw)

            results[country] = {
                "status": status,
                "label": label[:100],
                "stay": stay[:100],
                "notes": notes[:300] if notes else "",
                "color": STATUS_COLOURS.get(status, STATUS_COLOURS["unknown"]),
                "priority": STATUS_PRIORITY.get(status, 6),
            }

        # Don't break - process ALL tables to capture special territories (Greenland, etc.)

    results["_source_url"] = source_url
    return results


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("PHASE 2: Parsing cached HTML -> visa_data.json")
    print("=" * 60)

    index_path = CACHE_DIR / "_index.json"
    if not index_path.exists():
        raise SystemExit(f"No index found at {index_path}. Run download.py first!")

    index = json.loads(index_path.read_text())
    print(f"\nFound {len(index)} pages in index.\n")

    all_data = {}
    all_countries = set()
    skipped = []
    unknown_statuses = {}

    for i, entry in enumerate(index, 1):
        title = entry["title"]
        slug = entry["slug"]
        source_url = entry["url"]
        cache_path = CACHE_DIR / f"{slug}.html"

        # Skip partial-scope pages that don't contain regular nationality data
        skip_patterns = [
            "crew members",
            "EFTA nationals",
            "European Union citizens",
            "Sovereign Military Order of Malta",
            "Estonian non-citizens",
            "Latvian non-citizens",
            "Northern Cypriot citizens",
            "South Ossetian citizens",
            "Transnistrian citizens",
        ]
        if any(pattern in title for pattern in skip_patterns):
            print(f"[{i:03d}] SKIPPED (partial scope): {title}")
            skipped.append(title)
            continue

        if not cache_path.exists():
            print(f"[{i:03d}] MISSING: {title}")
            skipped.append(title)
            continue

        nationality = extract_nationality(title)
        html = cache_path.read_text(encoding="utf-8")
        page_data = parse_page(html, source_url)

        if len([k for k in page_data if not k.startswith("_")]) == 0:
            print(f"[{i:03d}] WARNING — no data parsed: {title}")
            skipped.append(title)
            continue

        all_data[nationality] = page_data
        all_countries.update(k for k in page_data if not k.startswith("_"))

        unknowns = [c for c, v in page_data.items()
                    if not c.startswith("_") and v["status"] == "unknown"]
        if unknowns:
            unknown_statuses[nationality] = unknowns

        n_countries = len([k for k in page_data if not k.startswith("_")])
        flag = f"  [{len(unknowns)} unknown]" if unknowns else ""
        print(f"[{i:03d}] {nationality}: {n_countries} countries{flag}")

    nationalities_sorted = sorted(all_data.keys())
    countries_sorted = sorted(all_countries)

    output = {
        "nationalities": nationalities_sorted,
        "countries": countries_sorted,
        "data": {k: all_data[k] for k in nationalities_sorted},
        "meta": {
            "total_nationalities": len(all_data),
            "total_countries": len(all_countries),
            "skipped": skipped,
        }
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\n" + "=" * 60)
    print(f"Done!")
    print(f"  Nationalities parsed : {len(all_data)}")
    print(f"  Unique destinations  : {len(all_countries)}")
    print(f"  Skipped              : {len(skipped)}")
    print(f"  Output               : {OUTPUT_FILE.resolve()}")

    if unknown_statuses:
        total_unknowns = sum(len(v) for v in unknown_statuses.values())
        print(f"\n  WARNING: {total_unknowns} unknowns across {len(unknown_statuses)} nationalities:")
        for nat, countries in list(unknown_statuses.items())[:8]:
            print(f"     {nat}: {countries[:4]}")
        if len(unknown_statuses) > 8:
            print(f"     ... and {len(unknown_statuses) - 8} more")
    else:
        print(f"\n  SUCCESS: No unknown statuses!")

    print("=" * 60)


if __name__ == "__main__":
    main()