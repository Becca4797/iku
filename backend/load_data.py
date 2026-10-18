"""
Load safety data into Tiger Data.

Run from the backend folder, with the virtual environment active:

    python load_data.py crime    --area ucl --months 1
    python load_data.py lighting --area ucl
    python load_data.py places   --area ucl
    python load_data.py all      --area london --months 6

Start with the small "ucl" test area. "london" is the whole prototype boundary
and takes a long time. Every run resumes where the last one stopped, because
finished tiles are recorded in the fetch_tiles table.

Data sources:
    crime:    data.police.uk (Open Government Licence)
    lighting: OpenStreetMap (c) OpenStreetMap contributors, ODbL
    places:   OpenStreetMap (c) OpenStreetMap contributors, ODbL
"""

import argparse
import math
import time

import requests
from psycopg.types.json import Jsonb

from config import GREATER_LONDON
from data import fetch_latest_crime_month
from database import get_connection

# (south, west, north, east)
AREAS = {
    "ucl": (51.5150, -0.1500, 51.5400, -0.1000),
    "london": GREATER_LONDON,
}

CRIME_TILE_DEG = 0.02   # about 2 km, keeps each request under the police 10,000 limit
OSM_TILE_DEG = 0.025    # about 2.5 km, split further automatically if a server struggles

POLICE_URL = "https://data.police.uk/api/crimes-street/all-crime"


# ---------------------------------------------------------------------------
# Overpass (OpenStreetMap) requests
# ---------------------------------------------------------------------------

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]

OVERPASS_HEADERS = {
    "User-Agent": "iku-safe-routes/0.1 (student project)",
    "Accept": "application/json",
}


def host(url):
    return url.split("/")[2]


def overpass(query):
    """Try each server in turn. Prints the real reason when one fails."""
    for server in OVERPASS_SERVERS:
        for attempt in range(2):
            try:
                response = requests.post(
                    server,
                    data={"data": query},
                    headers=OVERPASS_HEADERS,
                    timeout=100,
                )
            except requests.RequestException as error:
                print(f"    {host(server)}: {type(error).__name__}")
                break  # try the next server

            if response.status_code in (429, 504):
                print(f"    {host(server)}: busy (HTTP {response.status_code}), waiting")
                time.sleep(10 * (attempt + 1))
                continue

            if response.status_code != 200:
                print(f"    {host(server)}: HTTP {response.status_code}")
                break

            try:
                return response.json()["elements"]
            except (ValueError, KeyError):
                print(f"    {host(server)}: unreadable response")
                break

    raise RuntimeError("All Overpass servers failed")


def overpass_tile(build_query, tile, depth=0):
    """Fetch one tile. If every server fails, split it into four and retry."""
    try:
        return overpass(build_query(tile))
    except RuntimeError:
        if depth >= 2:
            raise
        print(f"    splitting tile (level {depth + 1})")
        s, w, n, e = tile
        mid_lat, mid_lon = (s + n) / 2, (w + e) / 2
        elements = []
        for part in (
            (s, w, mid_lat, mid_lon),
            (s, mid_lon, mid_lat, e),
            (mid_lat, w, n, mid_lon),
            (mid_lat, mid_lon, n, e),
        ):
            elements += overpass_tile(build_query, part, depth + 1)
            time.sleep(2)
        return elements


# ---------------------------------------------------------------------------
# Tiles and progress tracking
# ---------------------------------------------------------------------------

def make_tiles(bounds, step):
    """Split a bounding box into square-ish tiles."""
    south, west, north, east = bounds
    rows = math.ceil((north - south) / step - 1e-9)
    cols = math.ceil((east - west) / step - 1e-9)

    for r in range(rows):
        for c in range(cols):
            s = south + r * step
            w = west + c * step
            yield (s, w, min(s + step, north), min(w + step, east))


def tile_id(tile, step):
    return f"{tile[0]:.5f}_{tile[1]:.5f}_{step}"


def done_tiles(conn, feature, period=""):
    rows = conn.execute(
        "select tile from fetch_tiles where feature = %s and period = %s",
        (feature, period),
    ).fetchall()
    return {row[0] for row in rows}


def mark_done(conn, feature, tile, period, count):
    conn.execute(
        """
        insert into fetch_tiles (feature, tile, period, row_count)
        values (%s, %s, %s, %s)
        on conflict (feature, tile, period)
        do update set fetched_at = now(), row_count = excluded.row_count
        """,
        (feature, tile, period, count),
    )


def bbox(tile):
    s, w, n, e = tile
    return f"{s:.5f},{w:.5f},{n:.5f},{e:.5f}"


# ---------------------------------------------------------------------------
# Crime (police.uk)
# ---------------------------------------------------------------------------

def police_request(bounds, month, depth=0):
    """Fetch one tile. If the police API says it is too big, split it in four."""
    south, west, north, east = bounds
    polygon = ":".join([
        f"{south:.5f},{west:.5f}",
        f"{south:.5f},{east:.5f}",
        f"{north:.5f},{east:.5f}",
        f"{north:.5f},{west:.5f}",
    ])

    response = None
    for attempt in range(4):
        response = requests.get(
            POLICE_URL,
            params={"poly": polygon, "date": month},
            timeout=40,
        )
        if response.status_code == 429:  # rate limited: wait and retry
            time.sleep(3 * (attempt + 1))
            continue
        break

    if response.status_code == 503 and depth < 3:
        mid_lat = (south + north) / 2
        mid_lon = (west + east) / 2
        crimes = []
        for part in (
            (south, west, mid_lat, mid_lon),
            (south, mid_lon, mid_lat, east),
            (mid_lat, west, north, mid_lon),
            (mid_lat, mid_lon, north, east),
        ):
            crimes += police_request(part, month, depth + 1)
        return crimes

    response.raise_for_status()
    return response.json()


def recent_months(latest, count):
    year, month = map(int, latest.split("-"))
    months = []
    for _ in range(count):
        months.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return months


def load_crime(conn, bounds, months):
    latest = fetch_latest_crime_month()
    month_list = recent_months(latest, months)
    tiles = list(make_tiles(bounds, CRIME_TILE_DEG))
    failed = 0

    print(f"Crime: {len(tiles)} tiles x {len(month_list)} months ({', '.join(month_list)})")

    for month in month_list:
        done = done_tiles(conn, "crime", month)

        for number, tile in enumerate(tiles, 1):
            tid = tile_id(tile, CRIME_TILE_DEG)
            if tid in done:
                continue

            try:
                crimes = police_request(tile, month)
            except requests.RequestException as error:
                failed += 1
                print(f"  failed {month} tile {tid}: {type(error).__name__}")
                continue

            rows = []
            for crime in crimes:
                location = crime.get("location") or {}
                if (
                    crime.get("id") is None
                    or location.get("latitude") is None
                    or location.get("longitude") is None
                ):
                    continue
                rows.append((
                    crime["id"],
                    crime["category"],
                    crime["month"],
                    float(location["latitude"]),
                    float(location["longitude"]),
                ))

            with conn.cursor() as cursor:
                cursor.executemany(
                    """
                    insert into crimes (id, category, month, lat, lon)
                    values (%s, %s, %s, %s, %s)
                    on conflict (id) do nothing
                    """,
                    rows,
                )
            mark_done(conn, "crime", tid, month, len(rows))
            conn.commit()

            if number % 25 == 0:
                print(f"  {month}: tile {number}/{len(tiles)}")
            time.sleep(0.15)  # stay well under the police API rate limit

    conn.execute(
        """
        update features
        set fetch_date = now(), row_count = (select count(*) from crimes)
        where feature = 'crime'
        """
    )
    conn.commit()
    print(f"Crime done. Failed tiles: {failed} (run again to retry them).")


# ---------------------------------------------------------------------------
# Lighting (OpenStreetMap)
# ---------------------------------------------------------------------------

LIT_YES = {"yes", "24/7", "automatic", "sunset-sunrise"}
LIT_NO = {"no", "disused"}


def normalise_lit(value):
    if value in LIT_YES:
        return "yes"
    if value in LIT_NO:
        return "no"
    return None  # unclear tags are ignored


def lighting_query(tile):
    return f"""
    [out:json][timeout:60];
    (
      node["highway"="street_lamp"]({bbox(tile)});
      way["highway"]["lit"]({bbox(tile)});
    );
    out geom;
    """


def load_lighting(conn, bounds):
    tiles = list(make_tiles(bounds, OSM_TILE_DEG))
    done = done_tiles(conn, "lighting")
    failed = 0

    print(f"Lighting: {len(tiles)} tiles")

    for number, tile in enumerate(tiles, 1):
        tid = tile_id(tile, OSM_TILE_DEG)
        if tid in done:
            continue

        try:
            elements = overpass_tile(lighting_query, tile)
        except RuntimeError:
            failed += 1
            print(f"  failed tile {tid}")
            continue

        lamps = [
            (el["id"], el["lat"], el["lon"])
            for el in elements
            if el.get("type") == "node" and "lat" in el and "lon" in el
        ]

        streets = []
        for el in elements:
            if el.get("type") != "way":
                continue
            lit = normalise_lit(el.get("tags", {}).get("lit"))
            geometry = el.get("geometry", [])
            if lit is None or len(geometry) < 2:
                continue
            streets.append((
                el["id"],
                lit,
                Jsonb([[p["lat"], p["lon"]] for p in geometry]),
            ))

        with conn.cursor() as cursor:
            cursor.executemany(
                """
                insert into lamps (osm_id, lat, lon)
                values (%s, %s, %s)
                on conflict (osm_id) do nothing
                """,
                lamps,
            )
            cursor.executemany(
                """
                insert into lit_streets (osm_id, lit, points)
                values (%s, %s, %s)
                on conflict (osm_id)
                do update set lit = excluded.lit, points = excluded.points
                """,
                streets,
            )
        mark_done(conn, "lighting", tid, "", len(lamps) + len(streets))
        conn.commit()

        print(f"  tile {number}/{len(tiles)}: {len(lamps)} lamps, {len(streets)} lit streets")
        time.sleep(2)  # be polite to the public Overpass servers

    conn.execute(
        """
        update features
        set fetch_date = now(),
            row_count = (select count(*) from lamps) + (select count(*) from lit_streets)
        where feature = 'lighting'
        """
    )
    conn.commit()
    print(f"Lighting done. Failed tiles: {failed} (run again to retry them).")


# ---------------------------------------------------------------------------
# Places (OpenStreetMap)
# ---------------------------------------------------------------------------
# Maps OpenStreetMap tags onto the type names scoring.py already understands.

PLACE_RULES = [
    ("shop", {
        "convenience": "convenience_store",
        "supermarket": "supermarket",
        "chemist": "pharmacy",
    }),
    ("amenity", {
        "pharmacy": "pharmacy",
        "cafe": "cafe",
        "restaurant": "restaurant",
        "bar": "bar",
        "pub": "bar",
        "fast_food": "fast_food_restaurant",
        "hospital": "hospital",
        "police": "police",
    }),
]


def place_type(tags):
    for key, mapping in PLACE_RULES:
        found = mapping.get(tags.get(key))
        if found:
            return found
    return None


def places_query(tile):
    return f"""
    [out:json][timeout:60];
    (
      nwr["shop"~"^(convenience|supermarket|chemist)$"]({bbox(tile)});
      nwr["amenity"~"^(pharmacy|cafe|restaurant|bar|pub|fast_food|hospital|police)$"]({bbox(tile)});
    );
    out center tags;
    """


def load_places(conn, bounds):
    tiles = list(make_tiles(bounds, OSM_TILE_DEG))
    done = done_tiles(conn, "places")
    failed = 0

    print(f"Places: {len(tiles)} tiles")

    for number, tile in enumerate(tiles, 1):
        tid = tile_id(tile, OSM_TILE_DEG)
        if tid in done:
            continue

        try:
            elements = overpass_tile(places_query, tile)
        except RuntimeError:
            failed += 1
            print(f"  failed tile {tid}")
            continue

        rows = []
        for el in elements:
            tags = el.get("tags", {})
            kind = place_type(tags)
            centre = el if "lat" in el else el.get("center")

            if not kind or not centre:
                continue

            hours = tags.get("opening_hours")
            if hours is None and kind == "police":
                hours = "24/7"  # assumption: police stations count as always available

            rows.append((
                f"osm:{el['type']}:{el['id']}",
                tags.get("name"),
                [kind],
                centre["lat"],
                centre["lon"],
                hours,
            ))

        with conn.cursor() as cursor:
            cursor.executemany(
                """
                insert into places
                    (place_id, name, types, lat, lon, opening_hours_raw, source, fetched_at)
                values (%s, %s, %s, %s, %s, %s, 'OpenStreetMap', now())
                on conflict (place_id) do update set
                    name = excluded.name,
                    types = excluded.types,
                    lat = excluded.lat,
                    lon = excluded.lon,
                    opening_hours_raw = excluded.opening_hours_raw,
                    fetched_at = now()
                """,
                rows,
            )
        mark_done(conn, "places", tid, "", len(rows))
        conn.commit()

        print(f"  tile {number}/{len(tiles)}: {len(rows)} places")
        time.sleep(2)

    conn.execute(
        """
        update features
        set fetch_date = now(), row_count = (select count(*) from places)
        where feature = 'places'
        """
    )
    conn.commit()
    print(f"Places done. Failed tiles: {failed} (run again to retry them).")


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Load safety data into Tiger Data")
    parser.add_argument("what", choices=["crime", "lighting", "places", "all"])
    parser.add_argument("--area", choices=list(AREAS), default="ucl")
    parser.add_argument("--months", type=int, default=3, help="months of crime data")
    args = parser.parse_args()

    bounds = AREAS[args.area]

    with get_connection() as conn:
        if args.what in ("crime", "all"):
            load_crime(conn, bounds, args.months)
        if args.what in ("lighting", "all"):
            load_lighting(conn, bounds)
        if args.what in ("places", "all"):
            load_places(conn, bounds)


if __name__ == "__main__":
    main()