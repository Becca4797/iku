#CRIME SCORING AND KD-TREE: 
#each crime is weighted by offence type and recency, and that crimes recorded at the same anonymised location should be capped at 15.
from collections import defaultdict
from datetime import datetime
from math import isfinite

import numpy as np
from scipy.spatial import cKDTree
from astral import LocationInfo
from astral.sun import sun

from config import (
    WEIGHTS, CRIME_K, FAMILIAR_BONUS,
    SAFETY_THRESHOLD, WORST_WINDOW_SIZE,
    LONDON,
)
from geo import to_xy, haversine, resample, make_sections


CRIME_TYPE_WEIGHTS = {
    "violent-crime": 3.0,
    "robbery": 3.0,
    "possession-of-weapons": 2.0,
    "theft-from-the-person": 2.0,
    "public-order": 1.5,
    "anti-social-behaviour": 1.0,
    "criminal-damage-arson": 1.0,
    "drugs": 1.0,
    "burglary": 0.5,
    "shoplifting": 0.5,
    "other-theft": 0.5,
    "other-crime": 0.5,
    "vehicle-crime": 0.3,
    "bicycle-theft": 0.3,
}


def months_ago(month_string, reference_date):
    """Calculate the age of a crime record in months."""
    year, month = map(int, month_string.split("-")[:2])

    return max(
        0,
        (reference_date.year - year) * 12
        + reference_date.month - month
    )


def crime_weight(crime, reference_date):
    """Crime severity multiplied by recency decay."""
    severity = CRIME_TYPE_WEIGHTS.get(
        crime["category"], 0.5
    )

    age = months_ago(crime["month"], reference_date)

    return severity * (0.5 ** (age / 6))


def prepare_crimes(crimes, reference_date, cap=15):
    """
    Combine crimes at the same anonymised location,
    then cap their total weight.
    """
    totals = defaultdict(float)

    for crime in crimes:
        location = crime.get("location", {})
        lat = location.get("latitude")
        lon = location.get("longitude")

        if lat is None or lon is None:
            continue

        point = (float(lat), float(lon))

        totals[point] += crime_weight(
            crime, reference_date
        )

    return [
        (lat, lon, min(weight, cap))
        for (lat, lon), weight in totals.items()
    ]


class CrimeIndex:
    def __init__(self, prepared_crimes, K=CRIME_K):
        if K <= 0:
            raise ValueError("Crime calibration K must be positive")

        self.K = K
        self.weights = np.array(
            [c[2] for c in prepared_crimes],
            dtype=float
        )

        self.tree = (
            cKDTree([
                to_xy((c[0], c[1]))
                for c in prepared_crimes
            ])
            if prepared_crimes else None
        )

    def score(self, point):
        """Crime safety score in [0, 1] within 100 m."""
        if self.tree is None:
            return None  # No dataset, not zero crime

        indices = self.tree.query_ball_point(
            to_xy(point), r=100
        )

        raw = float(self.weights[indices].sum())

        return 1 / (1 + raw / self.K)



#STREET LIGHTING
#uses a KD-tree for street lamps and a spatial index for tagged streets. 
#three lamps within 50m give a score of 1, lit=yes gives a floor of 0.7, and lit=no gives a ceiling of 0.2.
from shapely.geometry import Point, LineString
from shapely.strtree import STRtree


class LightingIndex:
    def __init__(self, lamps, lit_streets):
        """
        lamps: list of (lat, lon)
        lit_streets: list of {
            "points": [(lat, lon), ...],
            "lit": "yes" or "no"
        }
        """
        self.lamp_count = len(lamps)

        self.lamp_tree = (
            cKDTree([to_xy(p) for p in lamps])
            if lamps else None
        )

        self.lines = []
        self.tags = []

        for street in lit_streets:
            if len(street["points"]) < 2:
                continue

            line = LineString([
                to_xy(p) for p in street["points"]
            ])

            self.lines.append(line)
            self.tags.append(street["lit"])

        self.street_tree = (
            STRtree(self.lines)
            if self.lines else None
        )

    def score(self, point):
        """Lighting safety score in [0, 1]."""
        if self.lamp_count < 5:
            score = 0.5  # Neutral missing-data fallback
        else:
            count = len(
                self.lamp_tree.query_ball_point(
                    to_xy(point), r=50
                )
            )
            score = min(1.0, count / 3)

        if self.street_tree is not None:
            xy = to_xy(point)
            nearby = self.street_tree.query(
                Point(xy).buffer(25)
            )

            if len(nearby):
                nearest = min(
                    nearby,
                    key=lambda i: self.lines[int(i)].distance(
                        Point(xy)
                    )
                )

                index = int(nearest)

                if self.lines[index].distance(Point(xy)) <= 25:
                    tag = self.tags[index]

                    if tag == "yes":
                        score = max(score, 0.7)
                    elif tag == "no":
                        score = min(score, 0.2)

        return score

#OPEN SHOPS AND SAFE PLACES
from datetime import timedelta

SAFE_TYPES = {"police", "hospital"}

FALLBACK_HOURS = {
    "convenience_store": (7, 23),
    "supermarket": (7, 22),
    "pharmacy": (9, 18),
    "cafe": (7, 17),
    "restaurant": (11, 23),
    "bar": (11, 23),
    "fast_food_restaurant": (11, 23),
    "meal_takeaway": (11, 23),
    "hospital": (0, 24),
}


def is_open(place, when):
    """Check opening hours at the intended walking time."""
    when = when.astimezone(LONDON)
    hours = place.get("regularOpeningHours")

    if hours and "periods" in hours:
        # Google uses Sunday=0, Monday=1, ...
        weekday = (when.weekday() + 1) % 7
        minute = (
            weekday * 1440
            + when.hour * 60
            + when.minute
        )

        for period in hours["periods"]:
            opening = period.get("open")
            closing = period.get("close")

            if not opening:
                continue

            if closing is None:
                return True  # 24-hour period

            start = (
                opening["day"] * 1440
                + opening.get("hour", 0) * 60
                + opening.get("minute", 0)
            )
            end = (
                closing["day"] * 1440
                + closing.get("hour", 0) * 60
                + closing.get("minute", 0)
            )

            if start <= end:
                if start <= minute < end:
                    return True
            elif minute >= start or minute < end:
                return True

        return False

    # Estimated hours when real hours are missing.
    hour = when.hour + when.minute / 60

    return any(
        start <= hour < end
        for place_type in place.get("types", [])
        if place_type in FALLBACK_HOURS
        for start, end in [FALLBACK_HOURS[place_type]]
    )


class ShopsIndex:
    def __init__(self, places):
        self.places = places

        valid = [
            place for place in places
            if "location" in place
        ]

        self.places = valid

        self.tree = (
            cKDTree([
                to_xy((
                    p["location"]["latitude"],
                    p["location"]["longitude"]
                ))
                for p in valid
            ])
            if valid else None
        )

    def score(self, point, when):
        """Open-business score within 100 m."""
        if self.tree is None:
            return 0.0

        nearby = self.tree.query_ball_point(
            to_xy(point), r=100
        )

        count = 0

        for i in nearby:
            place = self.places[i]

            if place.get(
                "businessStatus", "OPERATIONAL"
            ) != "OPERATIONAL":
                continue

            if not is_open(place, when):
                continue

            types = set(place.get("types", []))

            count += (
                2 if types.intersection(SAFE_TYPES)
                else 1
            )

        return min(1.0, count / 4)

#DAY/NIGHT WEIGHTS, FAMILIAR AREAS AND SECTION SCORING

def is_dark(when, latitude, longitude):
    """Use civil dawn and dusk in London."""
    if when.tzinfo is None:
        raise ValueError("Departure time must have a timezone")

    when = when.astimezone(LONDON)

    observer = LocationInfo(
        latitude=latitude,
        longitude=longitude
    ).observer

    times = sun(
        observer,
        date=when.date(),
        tzinfo=LONDON,
    )

    return when < times["dawn"] or when > times["dusk"]


def familiar_bonus(point, familiar_areas):
    """
    Familiar areas are:
    [(latitude, longitude, radius_metres), ...]
    """
    for lat, lon, radius in familiar_areas:
        if haversine(point, (lat, lon)) <= radius:
            return FAMILIAR_BONUS

    return 0.0


def weighted_point_score(
    crime, lights, shops, period, bonus=0.0
):
    """Weighted safety score in [0, 1]."""
    weights = WEIGHTS[period]

    values = (crime, lights, shops)

    if not all(
        v is not None
        and isfinite(v)
        and 0 <= v <= 1
        for v in values
    ):
        return None

    score = (
        weights["crime"] * crime
        + weights["lights"] * lights
        + weights["shops"] * shops
    )

    return min(1.0, score + bonus)


def route_safety(point_scores, window=3):
    """
    Return the route's 0–100 score and
    its lowest-scoring three-point stretch.
    """
    scores = np.asarray(point_scores, dtype=float)

    if len(scores) == 0 or not np.isfinite(scores).all():
        raise ValueError("Valid point scores are required")

    average = float(scores.mean())

    if len(scores) <= window:
        worst = average
        worst_i = 0
    else:
        windows = np.convolve(
            scores,
            np.ones(window) / window,
            mode="valid"
        )
        worst_i = int(windows.argmin())
        worst = float(windows[worst_i])

    return {
        "safety": round(
            100 * (0.7 * average + 0.3 * worst), 2
        ),
        "worst_i": worst_i,
        "worst_score": worst,
        "average_score": average,
    }


def evaluate_route(
    points,
    seconds,
    crime_index,
    lighting_index,
    shops_index,
    departure_time,
    familiar_areas=None,
    threshold=SAFETY_THRESHOLD,
):
    """
    Score a complete route and check every section.

    points must contain the full Google route geometry.
    """
    familiar_areas = familiar_areas or []
    sampled = resample(points, step=50)

    # Use the middle of the journey to determine darkness.
    midpoint_time = (
        departure_time
        + timedelta(seconds=seconds / 2)
    )

    midpoint = sampled[len(sampled) // 2]

    period = (
        "night"
        if is_dark(midpoint_time, *midpoint)
        else "day"
    )

    point_results = []

    for point in sampled:
        crime = crime_index.score(point)
        lights = lighting_index.score(point)
        shops = shops_index.score(point, midpoint_time)

        bonus = familiar_bonus(point, familiar_areas)

        score = weighted_point_score(
            crime, lights, shops, period, bonus
        )

        point_results.append({
            "point": point,
            "crime": crime,
            "lights": lights,
            "shops": shops,
            "score": score,
        })

    sections = make_sections(sampled)

    section_results = []

    for i, section in enumerate(sections):
        # Conservative prototype rule: use the
        # lower score of the two section endpoints.
        a = point_results[i]["score"]
        b = point_results[i + 1]["score"]

        score = (
            min(a, b)
            if a is not None and b is not None
            else None
        )

        section_results.append({
            **section,
            "safety_score": (
                round(score * 100, 2)
                if score is not None else None
            ),
            "data_available": score is not None,
            "passes_threshold": (
                score is not None
                and score * 100 >= threshold
            ),
        })

    all_scores = [
        item["score"]
        for item in point_results
    ]

    summary = (
        route_safety(all_scores)
        if all(s is not None for s in all_scores)
        else None
    )

    failed = [
        section
        for section in section_results
        if not section["passes_threshold"]
    ]

    verified = all(
        section["data_available"]
        for section in section_results
    )

    eligible = verified and not failed

    worst_section = (
        min(
            section_results,
            key=lambda s: (
                s["safety_score"]
                if s["safety_score"] is not None
                else -1
            )
        )
        if section_results else None
    )

    return {
        "eligible": eligible,
        "status": (
            "eligible" if eligible
            else "unverified" if not verified
            else "below_threshold"
        ),
        "safety": (
            summary["safety"] if summary else None
        ),
        "worst_score": (
            summary["worst_score"]
            if summary else None
        ),
        "worst_i": (
            summary["worst_i"]
            if summary else None
        ),
        "used_weights": period,
        "point_scores": point_results,
        "sections": section_results,
        "worst_section": worst_section,
    }
