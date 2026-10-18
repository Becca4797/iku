"""
Turns the dictionary returned by route_builder.build_routes() into plain,
JSON-safe data for the front end.

Points are sent as {"lat": ..., "lng": ...} because that is the shape the
Google Maps JavaScript API uses, so the front end can draw them directly.
"""

import math


def _number(value):
    """Convert numpy numbers/bools to plain Python and drop NaN/inf."""
    if hasattr(value, "item") and not isinstance(value, (list, tuple, dict)):
        value = value.item()

    if isinstance(value, float) and not math.isfinite(value):
        return None

    return value


def _point(p):
    return {"lat": float(p[0]), "lng": float(p[1])}


def _section(section):
    return {
        "section_number": section["section_number"],
        "start": _point(section["start"]),
        "end": _point(section["end"]),
        "safety_score": _number(section.get("safety_score")),
        "data_available": bool(section.get("data_available")),
        "passes_threshold": bool(section.get("passes_threshold")),
    }


def _worst_section(section):
    if not section:
        return None
    return _section(section)


def serialise_route(route):
    """Keep only what the front end needs (drops the heavy point_scores)."""
    return {
        "id": route.get("id"),
        "label": route.get("label"),
        "status": route.get("status"),
        "scoring_status": route.get("scoring_status"),
        "eligible": bool(route.get("eligible")),
        "verification_note": route.get("verification_note"),
        "safety": _number(route.get("safety")),
        "worst_score": _number(route.get("worst_score")),
        "used_weights": route.get("used_weights"),
        "seconds": _number(route.get("seconds")),
        "meters": _number(route.get("meters")),
        "provider": route.get("provider"),
        "pts": [_point(p) for p in route.get("pts", [])],
        "sections": [_section(s) for s in route.get("sections", [])],
        "worst_section": _worst_section(route.get("worst_section")),
    }


def serialise_result(result):
    """Serialise the whole build_routes() result."""
    return {
        "status": result["status"],
        "preference": result["preference"],
        "start": _point(result["start"]),
        "destination": _point(result["destination"]),
        "routes": [serialise_route(r) for r in result["routes"]],
        "candidate_count": result["candidate_count"],
        "eligible_count": result["eligible_count"],
        "errors": [str(e) for e in result["errors"]],
    }