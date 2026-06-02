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
    # ── Configure date range here ──────────────────────────────────────────────
    START = "2026-05-01"
    END   = "2026-05-17"   # update this daily, or use datetime.utcnow()
    # ──────────────────────────────────────────────────────────────────────────

    from datetime import datetime as _dt
    END = _dt.utcnow().strftime("%Y-%m-%d")   # always fetch up to today

    results = fetch_date_range(START, END)

    output_file = "results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total_events = sum(
        len(sc["events"])
        for d in results["data"]
        for sc in d["sportCompetitions"]
    )
    print(f"\nDone! {len(results['data'])} day-blocks, {total_events} total events → saved to {output_file}")

