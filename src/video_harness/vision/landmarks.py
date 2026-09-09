"""Landmark and geographic place recognition for drone/camera footage."""

from __future__ import annotations

import math
from typing import Any

# Specific famous landmarks with tight bounding radii
KNOWN_LANDMARKS = [
    {
        "name": "Perrine Bridge & Snake River Canyon",
        "keywords": ["perrine bridge", "canyon", "snake river"],
        "lat": 42.6008,
        "lon": -114.4539,
        "radius_km": 1.8,
        "significance": "Iconic BASE jumping bridge soaring 486ft over Snake River Canyon",
    },
    {
        "name": "Pillar Falls & Snake River Rapids",
        "keywords": ["pillar falls", "falls", "rapids"],
        "lat": 42.5985,
        "lon": -114.4300,
        "radius_km": 2.5,
        "significance": "Dramatic rock pillars and roaring cascades in Snake River Canyon",
    },
    {
        "name": "Shoshone Falls ('Niagara of the West')",
        "keywords": ["shoshone falls", "waterfall", "falls"],
        "lat": 42.5936,
        "lon": -114.4008,
        "radius_km": 2.5,
        "significance": "Higher than Niagara Falls, plunging 212ft into basalt canyons",
    },
    {
        "name": "Angel Lake Glacial Cirque",
        "keywords": ["angel lake", "lake", "cirque"],
        "lat": 41.0250,
        "lon": -115.0847,
        "radius_km": 3.0,
        "significance": "Alpine glacial tarn tucked under 10,000ft East Humboldt peaks",
    },
    {
        "name": "Bonneville Salt Flats",
        "keywords": ["bonneville", "salt flats", "speedway"],
        "lat": 40.7608,
        "lon": -113.8964,
        "radius_km": 15.0,
        "significance": "Blinding white expanses of ancient Lake Bonneville salt crust",
    },
    {
        "name": "Pequop Summit Pass",
        "keywords": ["pequop", "mountain pass"],
        "lat": 41.0714,
        "lon": -114.5450,
        "radius_km": 5.0,
        "significance": "High desert mountain pass crossing 7,575ft over the Pequop range",
    }
]


def identify_landmark(lat: float, lon: float) -> dict[str, Any] | None:
    """Identify landmark by GPS coordinate proximity."""
    for lm in KNOWN_LANDMARKS:
        # Haversine distance
        dlat = math.radians(lm["lat"] - lat)
        dlon = math.radians(lm["lon"] - lon)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat)) * math.cos(math.radians(lm["lat"])) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        dist_km = 6371.0 * c
        if dist_km <= lm["radius_km"]:
            res = dict(lm)
            res["distance_km"] = round(dist_km, 2)
            return res
    return None
