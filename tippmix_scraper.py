import requests
import json
import time
from datetime import datetime, timedelta

API_URL = "https://api.tippmix.hu/tippmix/result"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://www.tippmix.hu",
    "Referer": "https://www.tippmix.hu/",
}

def fetch_results(date: str, sport_id: int = 999, competition_group_id: int = 99999988, interval: int = 1):
    """Fetch results for a single date (YYYY-MM-DD)."""
    payload = {
        "competitionGroupId": competition_group_id,
        "competitionId": 0,
        "competitionType": None,
        "date": f"{date}T00:00:00.000Z",
        "interval": interval,
        "market": 0,
        "searchBy": "",
        "sportId": sport_id,
        "type": "date"
    }
    response = requests.post(API_URL, json=payload, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def fetch_date_range(start_date: str, end_date: str, delay: float = 1.0):
    """
    Fetch and merge results for every day between start_date and end_date (inclusive).
    Returns a single merged dict with a 'data' list covering all days.
    
    :param start_date: 'YYYY-MM-DD'
    :param end_date:   'YYYY-MM-DD'
    :param delay:      seconds to wait between requests (be polite!)
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end   = datetime.strptime(end_date,   "%Y-%m-%d")
    all_days = []

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        print(f"Fetching {date_str} ...", end=" ")
        try:
            data = fetch_results(date_str)
            days = data.get("data", [])
            all_days.extend(days)
            print(f"✓  ({sum(len(sc['events']) for d in days for sc in d['sportCompetitions'])} events)")
        except Exception as e:
            print(f"✗  ERROR: {e}")
        current += timedelta(days=1)
        time.sleep(delay)

    return {"data": all_days}


if __name__ == "__main__":
    import os

    output_file = "results.json"
    ABSOLUTE_START = "2026-05-01"   # earliest date we ever care about

    # ── Load existing results so we can merge rather than overwrite ────────────
    existing_days: list = []
    existing_dates: set = set()
    if os.path.exists(output_file):
        try:
            with open(output_file, encoding="utf-8") as f:
                existing = json.load(f)
            existing_days  = existing.get("data", [])
            existing_dates = {d["date"] for d in existing_days}
        except Exception:
            pass   # corrupt / empty file → start fresh

    # ── Determine START: day after the latest date we already have ─────────────
    if existing_dates:
        last_known = max(existing_dates)
        START = (datetime.strptime(last_known, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"Existing data through {last_known} — fetching from {START} onwards …")
    else:
        START = ABSOLUTE_START
        print(f"No existing data — fetching from {START} …")

    END = datetime.utcnow().strftime("%Y-%m-%d")

    if START > END:
        print("Already up-to-date — nothing to fetch.")
    else:
        new_results = fetch_date_range(START, END)

        # ── Merge: drop any existing days that overlap with new fetch, then combine
        new_dates  = {d["date"] for d in new_results["data"]}
        kept_days  = [d for d in existing_days if d["date"] not in new_dates]
        merged     = sorted(kept_days + new_results["data"], key=lambda d: d["date"])

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({"data": merged}, f, ensure_ascii=False, indent=2)

        total_events = sum(
            len(sc["events"])
            for d in merged
            for sc in d["sportCompetitions"]
        )
        print(f"\nDone! {len(merged)} day-blocks total ({len(new_results['data'])} new), "
              f"{total_events} total events → saved to {output_file}")

