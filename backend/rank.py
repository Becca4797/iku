
from math import isfinite

from config import RANKING_WEIGHTS
from geo import haversine


def filter_by_time(routes):
    """Remove routes with excessive detours."""
    if not routes:
        return []

    fastest = min(r["seconds"] for r in routes)

    limit = min(
        1.5 * fastest,
        fastest + 15 * 60,
    )

    return [
        r for r in routes
        if r["seconds"] <= limit
    ]


def overlap(a_points, b_points, tolerance=30):
    """Fraction of A's points near any point in B."""
    if not a_points or not b_points:
        return 0.0

    count = sum(
        1 for p in a_points
        if min(
            haversine(p, q) for q in b_points
        ) <= tolerance
    )

    return count / len(a_points)


def dedupe(routes):
    """Remove near-identical routes, keeping faster ones."""
    kept = []

    for route in sorted(
        routes, key=lambda r: r["seconds"]
    ):
        duplicate = any(
            overlap(route["pts"], existing["pts"]) >= 0.8
            and overlap(
                existing["pts"], route["pts"]
            ) >= 0.8
            for existing in kept
        )

        if not duplicate:
            kept.append(route)

    return kept


def normalise(values, minimum_range):
    """Min-max normalization with a tie tolerance."""
    low = min(values)
    high = max(values)

    if high - low < minimum_range:
        return [0.0] * len(values)

    return [
        (v - low) / (high - low)
        for v in values
    ]

#supports all three presets and returns up to four qualifying routes.
def rank_routes(routes, preference="balanced"):
    """
    Rank routes using travel time and safety.

    Only fully verified, threshold-passing routes
    are eligible for the final ranking.
    """
    if preference not in RANKING_WEIGHTS:
        raise ValueError("Unknown ranking preference")

    eligible = [
        dict(r)
        for r in routes
        if r.get("eligible") is True
        and r.get("safety") is not None
        and isfinite(r["safety"])
        and 0 <= r["safety"] <= 100
        and r.get("seconds", 0) > 0
    ]

    if not eligible:
        return []

    eligible = dedupe(filter_by_time(eligible))

    times = [r["seconds"] for r in eligible]
    risks = [100 - r["safety"] for r in eligible]

    time_norm = normalise(times, 60)
    risk_norm = normalise(risks, 3)

    w_time, w_safety = RANKING_WEIGHTS[preference]

    for route, t, risk in zip(
        eligible, time_norm, risk_norm
    ):
        route["ranking_cost"] = (
            w_time * t + w_safety * risk
        )

    eligible.sort(
        key=lambda r: (
            r["ranking_cost"],
            -r["safety"],
            r["seconds"],
        )
    )

    return eligible[:4]

#selects up to three distinct routes for the UI, consistent with the earlier build plan.
def label_routes(routes):
    """
    Pick distinct routes for the three UI labels.
    """
    if not routes:
        return []

    safest = max(routes, key=lambda r: r["safety"])
    fastest = min(routes, key=lambda r: r["seconds"])

    balanced = rank_routes(routes, "balanced")

    selected = []
    used = set()

    choices = [
        ("Safest", safest),
        ("Fastest", fastest),
    ] + [
        ("Balanced", r) for r in balanced
    ]

    for label, route in choices:
        key = route.get("id", id(route))

        if key in used:
            continue

        selected.append({
            **route,
            "label": label,
        })
        used.add(key)

        if len(selected) == 3:
            break

    return selected
