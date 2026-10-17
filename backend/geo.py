#file supplies distance calculations and splits Google's walking route into evenly spaced sample points
import math
from pyproj import Transformer

R = 6_371_000

TO_METRES = Transformer.from_crs(
    "EPSG:4326", "EPSG:27700", always_xy=True
)


def haversine(a, b):
    """Distance in metres between two (lat, lon) points."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * R * math.asin(min(1, math.sqrt(h)))


def to_xy(point):
    """Convert a London GPS point into metre coordinates."""
    lat, lon = point
    return TO_METRES.transform(lon, lat)


def bearing(a, b):
    """Compass bearing in degrees from point a to b."""
    lat1, lat2 = map(math.radians, (a[0], b[0]))
    dlon = math.radians(b[1] - a[1])

    x = math.sin(dlon) * math.cos(lat2)
    y = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2)
        * math.cos(dlon)
    )

    return (math.degrees(math.atan2(x, y)) + 360) % 360


def offset(point, direction, distance_m):
    """Move a point by distance_m along a compass bearing."""
    lat, lon = map(math.radians, point)
    theta = math.radians(direction)
    d = distance_m / R

    new_lat = math.asin(
        math.sin(lat) * math.cos(d)
        + math.cos(lat) * math.sin(d) * math.cos(theta)
    )

    new_lon = lon + math.atan2(
        math.sin(theta) * math.sin(d) * math.cos(lat),
        math.cos(d) - math.sin(lat) * math.sin(new_lat)
    )

    return (math.degrees(new_lat), math.degrees(new_lon))


def resample(points, step=50):
    """
    Return coordinates approximately every 50 metres
    along the full walking-route geometry.
    """
    if len(points) < 2:
        raise ValueError("Route must contain at least 2 points")

    # Remove consecutive duplicate coordinates.
    cleaned = [tuple(points[0])]

    for p in points[1:]:
        p = tuple(p)
        if haversine(cleaned[-1], p) > 0.001:
            cleaned.append(p)

    if len(cleaned) < 2:
        raise ValueError("Route has zero length")

    lengths = [
        haversine(a, b)
        for a, b in zip(cleaned, cleaned[1:])
    ]

    total = sum(lengths)
    targets = []
    d = 0.0

    while d < total:
        targets.append(d)
        d += step

    targets.append(total)

    output = []
    segment = 0
    travelled = 0.0

    for target in targets:
        while (
            segment < len(lengths) - 1
            and travelled + lengths[segment] < target
        ):
            travelled += lengths[segment]
            segment += 1

        a = cleaned[segment]
        b = cleaned[segment + 1]
        length = lengths[segment]

        fraction = (
            (target - travelled) / length
            if length > 0 else 0
        )
        fraction = max(0, min(1, fraction))

        output.append((
            a[0] + fraction * (b[0] - a[0]),
            a[1] + fraction * (b[1] - a[1]),
        ))

    return output


def make_sections(sample_points):
    """Make sections between consecutive sampled points."""
    return [
        {
            "section_number": i,
            "start": sample_points[i],
            "end": sample_points[i + 1],
            "midpoint": (
                (sample_points[i][0] + sample_points[i + 1][0]) / 2,
                (sample_points[i][1] + sample_points[i + 1][1]) / 2,
            ),
        }
        for i in range(len(sample_points) - 1)
    ]
