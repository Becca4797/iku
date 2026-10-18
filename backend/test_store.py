"""
Check that the data in Tiger Data and the scoring code work together.

Run from the backend folder:
    python test_store.py
"""

from datetime import datetime

from config import LONDON, SAFETY_THRESHOLD
from geo import haversine
from route_scoring import score_candidate
from store import get_counts, get_scorers

# UCL Main Quad to King's Cross station, a straight-line stand-in for a walk
START = (51.5246, -0.1340)
END = (51.5309, -0.1239)

WALKING_SPEED_M_PER_S = 1.4

print("Loading data from Tiger Data...")
scorers = get_scorers()

print("Rows loaded:")
for name, number in get_counts().items():
    print(f"  {name}: {number}")

distance = haversine(START, END)
seconds = distance / WALKING_SPEED_M_PER_S

route = {
    "id": "test_route",
    "pts": [START, END],
    "seconds": seconds,
    "meters": distance,
}

print(f"\nTest route: {distance:.0f} m, about {seconds / 60:.0f} minutes")

today = datetime.now(LONDON).date()

for label, hour in [("Midday", 12), ("Late night", 23)]:
    departure = datetime(today.year, today.month, today.day, hour, 0, tzinfo=LONDON)

    result = score_candidate(
        route,
        scorers,
        departure_time=departure,
        threshold=SAFETY_THRESHOLD,
    )

    points = result["point_scores"]

    def average(key):
        values = [p[key] for p in points if p[key] is not None]
        return sum(values) / len(values) if values else None

    worst = result["worst_section"]

    print(f"\n--- {label} ({hour}:00) ---")
    print("Weights used:     ", result["used_weights"])
    print("Safety score:     ", result["safety"])
    print("Status:           ", result["status"])
    print("Sections:         ", len(result["sections"]))
    print(f"Average crime:     {average('crime'):.2f}  (1 = safest)")
    print(f"Average lighting:  {average('lights'):.2f}")
    print(f"Average shops:     {average('shops'):.2f}")
    print("Worst section:    ", worst["section_number"], "score", worst["safety_score"])

print("\nDONE")