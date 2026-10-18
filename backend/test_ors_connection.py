
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

api_key = os.getenv("ORS_API_KEY")

if not api_key:
    print("FAIL: ORS_API_KEY was not found in backend/.env")
    raise SystemExit(1)

url = "https://api.openrouteservice.org/v2/directions/foot-walking/geojson"

payload = {
    "coordinates": [
        [-0.1340, 51.5246],  # UCL
        [-0.1239, 51.5309],  # King's Cross area
    ],
    "instructions": False,
}

print("Testing connection to OpenRouteService...")

try:
    with httpx.Client(timeout=60) as client:
        response = client.post(
            url,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )

    print("HTTP status:", response.status_code)

    if response.is_success:
        data = response.json()
        features = data.get("features", [])

        if features:
            summary = features[0]["properties"]["summary"]
            print("PASS: ORS returned a walking route.")
            print("Distance:", round(summary["distance"]), "metres")
            print("Duration:", round(summary["duration"]), "seconds")
        else:
            print("No route returned. Response:", response.text[:1000])
    else:
        print("ORS returned an error:")
        print(response.text[:1500])

except httpx.TimeoutException:
    print("FAIL: ORS did not respond within 60 seconds.")
except httpx.RequestError as exc:
    print("FAIL: Network/request error:", type(exc).__name__, str(exc))
