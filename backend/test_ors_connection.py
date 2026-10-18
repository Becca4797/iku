
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

api_key = os.getenv("ORS_API_KEY")

if not api_key:
    raise ValueError("ORS_API_KEY not found")

url = (
    "https://api.openrouteservice.org"
    "/v2/directions/foot-walking"
)

params = {
    "api_key": api_key,
    "start": "-0.1340,51.5246",
    "end": "-0.1325,51.5250",
}

print("Testing ORS directions endpoint...", flush=True)

try:
    response = requests.get(
        url,
        params=params,
        timeout=(10, 15),
    )

    print("HTTP status:", response.status_code)

    if response.ok:
        data = response.json()
        print("Routes returned:", len(data.get("features", [])))
        print("ORS CONNECTION SUCCESS!")
    else:
        print("API error:", response.text[:500])

except requests.exceptions.Timeout:
    print("ORS request timed out.")

except requests.exceptions.ConnectionError as error:
    print("Connection failed:", str(error)[:300])
