
from config import WEIGHTS
from geo import haversine, resample
from scoring import weighted_point_score, route_safety
from rank import rank_routes


# TEST 1: Check the day/night weights
for period, weights in WEIGHTS.items():
    assert abs(sum(weights.values()) - 1) < 1e-9

print("PASS: Day/night weights")


# TEST 2: Check the weighted safety score
score = weighted_point_score(
    crime=0.5,
    lights=1.0,
    shops=0.5,
    period="night"
)

assert abs(score - 0.675) < 1e-9

print("PASS: Weighted safety scoring")


# TEST 3: Check route distances
a = (51.5246, -0.1340)
b = (51.5309, -0.1239)

distance = haversine(a, b)

assert distance > 0

print("PASS: Distance calculation")


# TEST 4: Check 50m route sampling
points = resample([a, b], step=50)

assert len(points) > 2

print("PASS: Route sampling")


# TEST 5: Check worst-section detection
result = route_safety([
    0.9, 0.9, 0.2, 0.2, 0.2, 0.9, 0.9
])

assert result["worst_i"] == 2
assert abs(result["worst_score"] - 0.2) < 1e-9

print("PASS: Worst-section detection")


# TEST 6: Check route ranking
routes = [
    {
        "id": "A",
        "pts": [a, b],
        "seconds": 600,
        "safety": 90,
        "eligible": False,
    },
    {
        "id": "B",
        "pts": [a, b],
        "seconds": 700,
        "safety": 75,
        "eligible": True,
    },
]

ranked = rank_routes(routes, "balanced")

assert len(ranked) == 1
assert ranked[0]["id"] == "B"

print("PASS: Route ranking")

print("ALL TESTS PASSED!")
