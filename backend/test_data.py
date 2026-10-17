
from data import fetch_lamps, fetch_lit_streets

# Small area near UCL in central London
bounds = (
    51.520,
    -0.140,
    51.530,
    -0.125
)

print("Fetching OpenStreetMap data...")

lamps = fetch_lamps(bounds)
print("Street lamps found:", len(lamps))
print("First 5 lamps:", lamps[:5])

streets = fetch_lit_streets(bounds)
print("Streets with lighting tags:", len(streets))

print("DATA TEST COMPLETE!")
