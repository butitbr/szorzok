"""
prematch_collector.py
─────────────────────
Run this script every few minutes (e.g. via Windows Task Scheduler).
For every upcoming E-Sport event it:
  1. Fetches the event list  (POST /v2/tippmix/events)
  2. For each event, fetches all markets (GET /v2/tippmix/event/{id}/ungrouped)
  3. Extracts every Gólszám (O/U) market with odds
  4. Appends to a local SQLite database  →  prematch_odds.db
"""

import requests
import sqlite3
import time
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

DB_FILE   = "prematch_odds.db"
BASE_URL  = "https://api.tippmix.hu"
HEADERS   = {
    "Accept":       "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=utf-8",
    "Origin":       "https://www.tippmix.hu",
    "Referer":      "https://www.tippmix.hu/",
}

# ── Database setup ─────────────────────────────────────────────────────────────
def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prematch_odds (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at     TEXT,
            event_id         INTEGER,
            event_name       TEXT,
            event_date       TEXT,
            competition_name TEXT,
            market_id        INTEGER,
            threshold        REAL,
            outcome_name     TEXT,   -- 'OVER' or 'UNDER'
            odds             REAL,
            UNIQUE(collected_at, event_id, market_id, outcome_name)
        )
    """)
    conn.commit()

# ── API helpers ────────────────────────────────────────────────────────────────
def fetch_event_list(page_size=100):
    """Return all upcoming events (one page, increase page_size if needed)."""
    payload = {
        "competitionGroupId":  99999988,
        "competitionOrAliasId": None,
        "eventTypes":   [],
        "marketTypes":  [],
        "maxDate":  None,
        "maxOdds":  None,
        "minDate":  None,
        "minOdds":  None,
        "page":     1,
        "pageSize": page_size,
        "search":   None,
        "sportId":  999,
    }
    r = requests.post(
        f"{BASE_URL}/v2/tippmix/events?compatibility=v1",
        json=payload, headers=HEADERS, timeout=10
    )
    r.raise_for_status()
    return r.json().get("events", [])


def fetch_event_markets(event_id):
    """Return all markets for a single event."""
    r = requests.get(
        f"{BASE_URL}/v2/tippmix/event/{event_id}/ungrouped?compatibility=v1",
        headers=HEADERS, timeout=10
    )
    r.raise_for_status()
    data = r.json()
    # Response is {"event": {"markets": [...]}}
    if isinstance(data, dict) and "event" in data:
        return data["event"].get("markets", [])
    return data if isinstance(data, list) else data.get("markets", [])


# ── Main collection loop ───────────────────────────────────────────────────────
def collect():
    conn = sqlite3.connect(DB_FILE)
    init_db(conn)
    collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    logging.info("Fetching event list …")
    events = fetch_event_list()
    logging.info(f"  {len(events)} events found")

    inserted = 0
    for ev in events:
        event_id = ev["eventId"]
        try:
            markets = fetch_event_markets(event_id)
        except Exception as e:
            logging.warning(f"  Could not fetch markets for {event_id}: {e}")
            time.sleep(0.5)
            continue

        for m in markets:
            market_name = m.get("marketName", "")
            if "Gólszám" not in market_name:
                continue

            threshold = float(m.get("specialOddsValue") or 0)
            if threshold == 0:
                continue

            for outcome in m.get("outcomes", []):
                name = outcome.get("outcomeName", "")
                odds = outcome.get("fixedOdds")
                if odds is None:
                    continue
                direction = "OVER"  if "Több"     in name else \
                            "UNDER" if "Kevesebb" in name else name

                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO prematch_odds
                        (collected_at, event_id, event_name, event_date,
                         competition_name, market_id, threshold, outcome_name, odds)
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, (
                        collected_at,
                        event_id,
                        ev.get("eventName", ""),
                        ev.get("eventDate", ""),
                        ev.get("competitionName", ""),
                        m["marketId"],
                        threshold,
                        direction,
                        odds,
                    ))
                    inserted += conn.execute("SELECT changes()").fetchone()[0]
                except Exception as e:
                    logging.warning(f"  DB insert error: {e}")

        time.sleep(0.3)   # be polite – ~300 ms between per-event requests

    conn.commit()
    conn.close()
    logging.info(f"Done — {inserted} new rows inserted into {DB_FILE}")


if __name__ == "__main__":
    import sys
    if "--loop" in sys.argv:
        logging.info("Starting hourly loop. Press Ctrl+C to stop.")
        while True:
            try:
                collect()
            except Exception as e:
                logging.error(f"Collection failed: {e}")
            logging.info("Sleeping 1 hour …")
            time.sleep(3600)
    else:
        collect()
