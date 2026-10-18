
import asyncio
from pathlib import Path

import httpx
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parent / ".env")

GOOGLE_KEY = os.getenv("GOOGLE_ROUTES_API_KEY")
ORS_KEY = os.getenv("ORS_API_KEY")

# UCL Main Quad to King's Cross Station
START = (51.5246, -0.1340)
DESTINATION = (51.5309, -0.1239)


async def main():
    async with httpx.AsyncClient(timeout=60) as client:
        print("Testing Google Routes API...")

        if not GOOGLE_KEY:
            print("FAIL: GOOGLE_ROUTES_API_KEY is missing.")
        else:
            try:
                response = await client.post(
                    "https://routes.googleapis.com/directions/v2:computeRoutes",
                    headers={
                        "Content-Type": "application/json",
                        "X-Goog-Api-Key": GOOGLE_KEY,
                        "X-Goog-FieldMask": (
                            "routes.duration,routes.distanceMeters,"
                            "routes.polyline.encodedPolyline"
                        ),
                    },
                    json={
                        "origin": {
                            "location": {
                                "latLng": {
                                    "latitude": START[0],
                                    "longitude": START[1],
                                }
                            }
                        },
                        "destination": {
                            "location": {
                                "latLng": {
                                    "latitude": DESTINATION[0],
                                    "longitude": DESTINATION[1],
                                }
                            }
                        },
                        "travelMode": "WALK",
                    },
                )

                if response.is_success:
                    routes = response.json().get("routes", [])
                    if routes:
                        print("PASS: Google returned a walking route.")
                        print("Distance:", routes[0].get("distanceMeters"), "metres")
                        print("Duration:", routes[0].get("duration"), "seconds")
                    else:
                        print("FAIL: Google returned no routes.")
                        print(response.text[:500])
                else:
                    print("FAIL: Google returned HTTP", response.status_code)
                    print(response.text[:500])

            except httpx.HTTPError as exc:
                print("FAIL: Google request error:", exc)

        print("\nTesting OpenRouteService...")

        if not ORS_KEY:
            print("FAIL: ORS_API_KEY is missing.")
        else:
            try:
                response = await client.post(
                    "https://api.openrouteservice.org/v2/directions/foot-walking/geojson",
                    headers={
                        "Authorization": ORS_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "coordinates": [
                            [START[1], START[0]],
                            [DESTINATION[1], DESTINATION[0]],
                        ],
                        "instructions": False,
                    },
                )

                if response.is_success:
                    features = response.json().get("features", [])
                    if features:
                        summary = features[0]["properties"]["summary"]
                        print("PASS: ORS returned a walking route.")
                        print("Distance:", round(summary["distance"]), "metres")
                        print("Duration:", round(summary["duration"]), "seconds")
                    else:
                        print("FAIL: ORS returned no routes.")
                        print(response.text[:500])
                else:
                    print("FAIL: ORS returned HTTP", response.status_code)
                    print(response.text[:500])

            except httpx.HTTPError as exc:
                print("FAIL: ORS request error:", type(exc).__name__, repr(exc))


if __name__ == "__main__":
    asyncio.run(main())
