
from scoring import (
    CrimeIndex,
    LightingIndex,
    ShopsIndex,
    evaluate_route,
)


def build_scorers(
    prepared_crimes,
    lamps,
    lit_streets,
    places,
    crime_K,
):
    """
    Build the spatial indexes used for safety scoring.
    Only needs to run once per set of safety data.
    """
    return {
        "crime": CrimeIndex(
            prepared_crimes,
            K=crime_K,
        ),
        "lighting": LightingIndex(
            lamps,
            lit_streets,
        ),
        "shops": ShopsIndex(
            places,
        ),
    }


def score_candidate(
    route,
    scorers,
    departure_time,
    familiar_areas=None,
    threshold=60,
):
    """
    Score a complete route from Google Maps.

    Expected route format:
    {
        "id": "route_1",
        "pts": [(latitude, longitude), ...],
        "seconds": 780,
        "meters": 1100
    }
    """
    result = evaluate_route(
        points=route["pts"],
        seconds=route["seconds"],
        crime_index=scorers["crime"],
        lighting_index=scorers["lighting"],
        shops_index=scorers["shops"],
        departure_time=departure_time,
        familiar_areas=familiar_areas,
        threshold=threshold,
    )

    return {
        **route,
        **result,
    }
