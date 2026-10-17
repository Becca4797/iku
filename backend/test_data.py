
from data import fetch_lamps, fetch_lit_streets

# Very small area near UCL
bounds = (
    51.5235,
    -0.1355,
    51.5255,
    -0.1325
)


print("Fetching OpenStreetMap data...")

lamps = fetch_lamps(bounds)
print("Street lamps found:", len(lamps))
print("First 5 lamps:", lamps[:5])

streets = fetch_lit_streets(bounds)
print("Streets with lighting tags:", len(streets))

print("DATA TEST COMPLETE!")
