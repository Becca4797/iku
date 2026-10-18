
import asyncio
import os
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from config import (
    LONDON,
    SAFETY_THRESHOLD,
)
from geo import haversine
from rank import rank_routes, label_routes
from route_scoring import score_candidate
from store import get_scorers


# Load backend/.env regardless of the directory used to launch Python.
load_dotenv(Path(__file__).resolve().parent / ".env")

GOOGLE_ROUTES_URL = (
    "https://routes.googleapis.com/directions/v2:computeRoutes"
)
GOOGLE_KEY = os.getenv("GOOGLE_ROUTES_API_KEY")

HTTP_TIMEOUT_SECONDS = 30


class RouteBuildError(Exception):
    """Raised when route generation cannot continue."""


def _validate_point(point, name):
    """Validate a latitude/longitude pair."""
    if not isinstance(point, (tuple, list)) or len(point) != 2:
        raise ValueError(
            f"{name} must be a (latitude, longitude) pair"
        )

    lat, lon = float(point[0]), float(point[1])

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"{name} has invalid coordinates")

    return lat, lon


def _decode_polyline(encoded):
    """Decode Google's encoded polyline into (latitude, longitude) pairs."""
    points = []
    index = 0
    lat = 0
    lon = 0

    while index < len(encoded):
        values = []

        for _ in range(2):
            result = 0
            shift = 0

            while True:
                if index >= len(encoded):
                    raise RouteBuildError(
                        "Invalid encoded route polyline"
                    )

                byte = ord(encoded[index]) - 63
                index += 1

                result |= (byte & 0x1F) << shift
                shift += 5

                if byte < 0x20:
                    break

            delta = (
                ~(result >> 1)
                if result & 1
                else result >> 1
            )
            values.append(delta)

        lat += values[0]
        lon += values[1]
        points.append((lat / 1e5, lon / 1e5))

    if len(points) < 2:
        raise RouteBuildError(
            "Google returned insufficient route geometry"
        )

    return points


async def _google_routes(client, start, destination):
    """Request Google's available complete walking-route alternatives."""
    if not GOOGLE_KEY:
        raise RouteBuildError(
            "GOOGLE_ROUTES_API_KEY is missing from backend/.env"
        )

    response = await client.post(
        GOOGLE_ROUTES_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_KEY,
            "X-Goog-FieldMask": (
                "routes.duration,"
                "routes.distanceMeters,"
                "routes.polyline.encodedPolyline,"
                "routes.routeLabels"
            ),
        },
        json={
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": start[0],
                        "longitude": start[1],
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": destination[0],
                        "longitude": destination[1],
                    }
                }
            },
            "travelMode": "WALK",
            "computeAlternativeRoutes": True,
        },
    )

    response.raise_for_status()
    data = response.json()
    items = data.get("routes", [])

    if not items:
        raise RouteBuildError(
            "Google Routes returned no walking routes"
        )

    routes = []

    for item in items:
        duration = item["duration"].removesuffix("s")

        routes.append({
            "pts": _decode_polyline(
                item["polyline"]["encodedPolyline"]
            ),
            "seconds": float(duration),
            "meters": float(item["distanceMeters"]),
            "provider": "google",
            "google_labels": item.get("routeLabels", []),
        })

    return routes


def _route_signature(points, precision=4):
    """Create a rough geometry signature for duplicate detection."""
    if not points:
        return ()

    stride = max(1, len(points) // 20)
    chosen = points[::stride]

    if chosen[-1] != points[-1]:
        chosen.append(points[-1])

    return tuple(
        (round(lat, precision), round(lon, precision))
        for lat, lon in chosen
    )


async def build_routes(
    start,
    destination,
    preference="balanced",
    departure_time=None,
    familiar_areas=None,
):
    """
    Request Google's complete A-to-B walking alternatives, score them,
    and rank the eligible routes.

    This version uses Google Routes only. It does not force routes around
    a dangerous area, and it does not persist route records to the database.
    """
    start = _validate_point(start, "start")
    destination = _validate_point(destination, "destination")

    if haversine(start, destination) < 1:
        raise ValueError("Start and destination must be different")

    if departure_time is None:
        departure_time = datetime.now(LONDON)
    elif departure_time.tzinfo is None:
        raise ValueError(
            "departure_time must include a timezone"
        )

    scorers = await asyncio.to_thread(get_scorers)

    candidates = []
    signatures = set()
    errors = []

    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS
    ) as client:
        try:
            raw_routes = await _google_routes(
                client, start, destination
            )

            for index, raw_route in enumerate(raw_routes, start=1):
                signature = _route_signature(raw_route["pts"])

                if signature in signatures:
                    continue

                signatures.add(signature)

                raw_route["id"] = f"route_{index}"
                raw_route["start"] = start
                raw_route["destination"] = destination

                scored = await asyncio.to_thread(
                    score_candidate,
                    raw_route,
                    scorers,
                    departure_time,
                    familiar_areas,
                    SAFETY_THRESHOLD,
                )

                candidates.append(scored)

        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            RouteBuildError,
        ) as exc:
            errors.append(f"Google routing error: {exc}")

    ranked = rank_routes(candidates, preference)
    labelled = label_routes(ranked)

    return {
        "start": start,
        "destination": destination,
        "preference": preference,
        "routes": labelled,
        "candidate_count": len(candidates),
        "eligible_count": sum(
            route.get("eligible") is True
            for route in candidates
        ),
        "errors": errors,
        "status": "ok" if labelled else "no_eligible_routes",
    }
