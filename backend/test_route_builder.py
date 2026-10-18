
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from route_builder import build_routes


async def main():
    # UCL Main Quad -> King's Cross Station
    start = (51.5246, -0.1340)
    destination = (51.5309, -0.1239)

    print("Building routes...")
    result = await build_routes(
        start=start,
        destination=destination,
        preference="balanced",
        departure_time=datetime.now(ZoneInfo("Europe/London")),
    )

    print("\nStatus:", result["status"])
    print("Candidates scored:", result["candidate_count"])
    print("Eligible candidates:", result["eligible_count"])

    if result["errors"]:
        print("\nErrors:")
        for error in result["errors"]:
            print("-", error)

    if not result["routes"]:
        print("\nNo eligible routes were returned.")
        print("This may be due to the safety threshold or data coverage.")
        return

    print("\nRanked routes:")
    for route in result["routes"]:
        print("-" * 40)
        print("ID:", route.get("id"))
        print("Label:", route.get("label"))
        print("Distance:", round(route.get("meters", 0)), "m")
        print("Duration:", round(route.get("seconds", 0) / 60), "minutes")
        print("Safety:", route.get("safety"))
        print("Eligible:", route.get("eligible"))
        print("Status:", route.get("status"))


if __name__ == "__main__":
    asyncio.run(main())
