"""
Reads the safety data from Tiger Data and builds the scorers.

Usage from other code:
    from store import get_scorers
    scorers = get_scorers()      # loads once, then reuses

The scorers are the same objects route_scoring.build_scorers() always made:
scorers["crime"], scorers["lighting"], scorers["shops"].
"""

import threading
from datetime import datetime

from config import CRIME_K, LONDON
from database import get_connection
from route_scoring import build_scorers
from scoring import prepare_crimes

# A place open "24/7" in OpenStreetMap becomes one period with no closing time,
# which is the format scoring.is_open() treats as always open.
ALWAYS_OPEN = {"periods": [{"open": {"day": 0, "hour": 0, "minute": 0}}]}


# ---------------------------------------------------------------------------
# Database rows -> the shapes scoring.py expects
# ---------------------------------------------------------------------------

def crimes_from_rows(rows):
    # rows: (category, month, lat, lon)
    return [
        {
            "category": category,
            "month": month,
            "location": {"latitude": lat, "longitude": lon},
        }
        for category, month, lat, lon in rows
    ]


def lamps_from_rows(rows):
    # rows: (lat, lon)
    return [(lat, lon) for lat, lon in rows]


def streets_from_rows(rows):
    # rows: (lit, points) where points is [[lat, lon], ...]
    return [
        {"lit": lit, "points": [(p[0], p[1]) for p in points]}
        for lit, points in rows
    ]


def places_from_rows(rows):
    # rows: (types, lat, lon, business_status, opening_hours_raw)
    places = []

    for types, lat, lon, status, hours_raw in rows:
        place = {
            "types": list(types or []),
            "location": {"latitude": lat, "longitude": lon},
            "businessStatus": status or "OPERATIONAL",
        }

        if hours_raw and hours_raw.strip() == "24/7":
            place["regularOpeningHours"] = ALWAYS_OPEN
        # Any other hours text is not parsed yet, so scoring.is_open() falls
        # back to its estimated hours for the place type.

        places.append(place)

    return places


def build_from_rows(crime_rows, lamp_rows, street_rows, place_rows, reference_date):
    prepared = prepare_crimes(crimes_from_rows(crime_rows), reference_date)

    scorers = build_scorers(
        prepared_crimes=prepared,
        lamps=lamps_from_rows(lamp_rows),
        lit_streets=streets_from_rows(street_rows),
        places=places_from_rows(place_rows),
        crime_K=CRIME_K,
    )

    counts = {
        "crimes": len(crime_rows),
        "crime_locations": len(prepared),
        "lamps": len(lamp_rows),
        "lit_streets": len(street_rows),
        "places": len(place_rows),
    }

    return scorers, counts


# ---------------------------------------------------------------------------
# Loading from Tiger Data
# ---------------------------------------------------------------------------

def load_scorers():
    """Read all four tables and build fresh scorers. Returns (scorers, counts)."""
    with get_connection() as conn:
        crime_rows = conn.execute(
            "select category, month, lat, lon from crimes"
        ).fetchall()
        lamp_rows = conn.execute("select lat, lon from lamps").fetchall()
        street_rows = conn.execute("select lit, points from lit_streets").fetchall()
        place_rows = conn.execute(
            "select types, lat, lon, business_status, opening_hours_raw from places"
        ).fetchall()

    return build_from_rows(
        crime_rows, lamp_rows, street_rows, place_rows, datetime.now(LONDON)
    )


_lock = threading.Lock()
_scorers = None
_counts = None


def get_scorers():
    """Load once, then reuse. Safe to call from several requests at once."""
    global _scorers, _counts

    with _lock:
        if _scorers is None:
            _scorers, _counts = load_scorers()
        return _scorers


def get_counts():
    return _counts


def reload_scorers():
    """Call after running load_data.py to pick up new data without a restart."""
    global _scorers, _counts

    with _lock:
        _scorers, _counts = load_scorers()
        return _counts