
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load your API key from backend/.env
load_dotenv(Path(__file__).parent / ".env")

ORS_URL = (
    "https://api.openrouteservice.org"
    "/v2/directions/foot-walking/geojson"
)


def get_ors_route(origin, destination, avoid_polygon=None):
    """
    Get a walking route using openrouteservice.

    origin and destination: (latitude, longitude)

    avoid_polygon: optional GeoJSON polygon specifying
    an area the route should avoid.

    Returns a dictionary containing route coordinates,
    walking duration and distance.
    """

    api_key = os.getenv("ORS_API_KEY")

    if not api_key:
        raise ValueError(
            "ORS_API_KEY missing from backend/.env"
        )

    # ORS expects longitude BEFORE latitude
    payload = {
        "coordinates": [
            [origin[1], origin[0]],
            [destination[1], destination[0]],
        ],
        "instructions": False,
    }

    # Optional: avoid an unsafe area
    if avoid_polygon is not None:
        payload["options"] = {
            "avoid_polygons": avoid_polygon
        }

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/geo+json",
    }

    response = requests.post(
        ORS_URL,
        json=payload,
        headers=headers,
        timeout=45,
    )

    if not response.ok:
        raise RuntimeError(
            f"ORS API error {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()
    features = data.get("features", [])

    if not features:
        raise RuntimeError(
            "ORS returned no walking route"
        )

    feature = features[0]

    coordinates = feature["geometry"]["coordinates"]
    summary = feature["properties"]["summary"]

    # Convert ORS [longitude, latitude]
    # into Ding (latitude, longitude)
    points = [
        (coord[1], coord[0])
        for coord in coordinates
    ]

    return {
        "id": "ors_route",
        "provider": "openrouteservice",
        "pts": points,
        "seconds": float(summary["duration"]),
        "meters": float(summary["distance"]),
    }
