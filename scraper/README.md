# Visa Mapper — Scraper

## Setup

```bash
pip install beautifulsoup4
```

## Usage

### Step 1 — Download (run once)
```bash
python download.py
```
Fetches all ~216 Wikipedia visa pages into `cache/`. Takes a few minutes.
Safe to interrupt and re-run — already-cached pages are skipped.

### Step 2 — Parse (run whenever you like)
```bash
python parse.py
```
Reads from `cache/`, outputs `visa_data.json`. No network calls.
Tweak the `normalise_status()` function in `parse.py` and re-run instantly.

## Output format

```json
{
  "nationalities": ["Afghan", "Albanian", ...],
  "countries": ["Afghanistan", "Albania", ...],
  "data": {
    "British": {
      "France": {
        "status": "visa_free",
        "label": "Visa not required",
        "stay": "90 days",
        "color": "#2ecc71",
        "priority": 0
      },
      ...
    }
  }
}
```

## Visa status hierarchy (for AND/OR logic)

| Priority | Status | Meaning |
|----------|--------|---------|
| 0 | `visa_free` / `freedom_of_movement` | No action needed |
| 1 | `eta` | Lightweight electronic pre-approval (ESTA, eTA etc.) |
| 2 | `evisa` | Apply online in advance |
| 3 | `visa_on_arrival` / `evisa_or_voa` | Obtain at border or online |
| 4 | `visa_required` | Embassy application required |
| 5 | `admission_refused` | Entry not permitted |

**Multi-passport OR logic:** take the lowest priority number across passports.  
**Group AND logic:** take the highest priority number across travellers.
