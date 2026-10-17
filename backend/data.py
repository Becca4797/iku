
import json
from pathlib import Path

import requests

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def cached_json(name, fetch_function):
    """Read a cached response or fetch and save it."""
    path = CACHE_DIR / f"{name}.json"

    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    data = fetch_function()

    path.write_text(
        json.dumps(data),
        encoding="utf-8"
    )

    return data


def fetch_latest_crime_month():
    """Find the most recent police crime-data month."""
    response = requests.get(
        "https://data.police.uk/api/crime-last-updated",
        timeout=20,
    )
    response.raise_for_status()

    return response.json()["date"][:7]


def fetch_crimes(bounds, month):
    """
    Fetch reported street crimes for one month.

    bounds = (south, west, north, east)
    """
    south, west, north, east = bounds

    polygon = ":".join([
        f"{south},{west}",
        f"{south},{east}",
        f"{north},{east}",
        f"{north},{west}",
    ])

    def request():
        response = requests.get(
            "https://data.police.uk/api/crimes-street/all-crime",
            params={
                "poly": polygon,
                "date": month,
            },
            timeout=40,
        )
        response.raise_for_status()
        return response.json()

    key = (
        f"crime_{month}_"
        f"{south:.5f}_{west:.5f}_"
        f"{north:.5f}_{east:.5f}"
    )

    return cached_json(key, request)




def overpass_query(query, cache_key):
    """Fetch OpenStreetMap data with server fallback."""

    servers = [
        "https://overpass.private.coffee/api/interpreter",
        "https://overpass.nchc.org.tw/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]

    def request():
        last_error = None

        for server in servers:
            try:
                print("Trying Overpass:", server)

                response = requests.post(
                    server,
                    data={"data": query},
                    headers={
                        "User-Agent": "DingHackathonPrototype/1.0",
                        "Accept": "application/json",
                    },
                    timeout=45,
                )

                response.raise_for_status()

                return response.json()["elements"]

            except (
                requests.exceptions.RequestException,
                ValueError,
                KeyError,
            ) as error:
                print("Server failed:", type(error).__name__)
                last_error = error

        raise RuntimeError(
            "All Overpass servers failed"
        ) from last_error

    return cached_json(cache_key, request)




def fetch_lamps(bounds):
    south, west, north, east = bounds

    query = f"""
    [out:json][timeout:60];
    node["highway"="street_lamp"]
    ({south},{west},{north},{east});
    out;
    """

    key = (
        f"lamps_{south:.5f}_{west:.5f}_"
        f"{north:.5f}_{east:.5f}"
    )

    elements = overpass_query(query, key)

    return [
        (item["lat"], item["lon"])
        for item in elements
        if "lat" in item and "lon" in item
    ]


def fetch_lit_streets(bounds):
    south, west, north, east = bounds

    query = f"""
    [out:json][timeout:60];
    way["highway"]["lit"]
    ({south},{west},{north},{east});
    out geom;
    """

    key = (
        f"lit_{south:.5f}_{west:.5f}_"
        f"{north:.5f}_{east:.5f}"
    )

    elements = overpass_query(query, key)
    streets = []

    for item in elements:
        geometry = item.get("geometry", [])

        if len(geometry) < 2:
            continue

        streets.append({
            "points": [
                (p["lat"], p["lon"])
                for p in geometry
            ],
            "lit": item.get("tags", {}).get("lit"),
        })

    return streets
