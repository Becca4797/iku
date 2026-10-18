
from ors_routing import get_ors_route

# UCL to King's Cross
origin = (51.5246, -0.1340)
destination = (51.5250, -0.1325)

print("Requesting walking route...")

route = get_ors_route(origin, destination)

print("Distance:", route["meters"], "metres")
print("Duration:", route["seconds"], "seconds")
print("Number of points:", len(route["pts"]))
print("First 5 points:", route["pts"][:5])

print("ORS INITIAL ROUTE SUCCESS!")
