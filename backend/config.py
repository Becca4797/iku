
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

DATABASE_URL = os.getenv("TIMESCALE_SERVICE_URL")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

LONDON = ZoneInfo("Europe/London")

# Prototype boundary, not the exact Greater London boundary
GREATER_LONDON = (51.28, -0.51, 51.70, 0.33)

WEIGHTS = {
    "day": {
        "crime": 0.60,
        "lights": 0.10,
        "shops": 0.30,
    },
    "night": {
        "crime": 0.40,
        "lights": 0.35,
        "shops": 0.25,
    },
}

# Provisional: calibrate using real London data
SAFETY_THRESHOLD = 60.0
CRIME_K = 10.0

SAMPLE_DISTANCE_M = 50
CRIME_RADIUS_M = 100
LIGHT_RADIUS_M = 50
SHOP_RADIUS_M = 100

FAMILIAR_BONUS = 0.10
WORST_WINDOW_SIZE = 3

MAX_ROUTE_REQUESTS = 5
MAX_QUALIFYING_ROUTES = 4

RANKING_WEIGHTS = {
    "safest": (0.20, 0.80),
    "balanced": (0.50, 0.50),
    "fastest": (0.80, 0.20),
}

