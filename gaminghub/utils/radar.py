"""
Radar-chart geometry.

The skill radar is server-rendered inline SVG rather than a charting
library: it sits in the landing-page hero, so it must paint with the
first byte (no CDN round-trip, no layout shift as a canvas initialises)
and it has to inherit the design tokens the rest of the page uses.
Chart.js is still used on the analytics page, where a heavier
interactive chart below the fold is a reasonable trade.

This module does the maths only -- it returns plain dicts of numbers and
knows nothing about colour or markup. templates/_radar.html draws them.
"""

import math


# Drawn labels, where the skill's real name is too long to sit beside
# the chart without either shrinking the radar or running off the edge.
# The full name is still rendered into the SVG <title>, so screen
# readers and tooltips get the real taxonomy.
SHORT_LABELS = {
    "Pattern Recognition": "Patterns",
    "Decision Making": "Decisions",
    "Multitasking": "Multitask",
}


def _vertices(cx, cy, radius, count, start=-math.pi / 2):
    """`count` points evenly spaced on a circle, first one at the top."""
    step = 2 * math.pi / count
    return [
        (
            round(cx + radius * math.cos(start + i * step), 2),
            round(cy + radius * math.sin(start + i * step), 2),
        )
        for i in range(count)
    ]


def _to_points(vertices):
    """SVG polygon `points` attribute from a list of (x, y)."""
    return " ".join(f"{x},{y}" for x, y in vertices)


def _label_anchor(cx, x):
    """
    Horizontal anchoring for a label sitting outside its vertex. Labels
    near the vertical axis read best centred; the rest hang off the side
    they're on, so long ones like "Pattern Recognition" grow outward
    instead of back across the chart.
    """
    offset = x - cx
    if abs(offset) < 12:
        return "middle"
    return "start" if offset > 0 else "end"


def build_radar(profile, size=340, padding=64, rings=4, compare=None):
    """
    Turn a skill profile into everything the SVG template needs.

    profile: list of {"skill", "score" (0-100), "plays"} -- every axis,
             including unplayed ones (see analytics_service.get_radar_profile).
    compare: an optional second profile of the same shape and order,
             drawn as an outline behind the main polygon.

    Returns None for an empty profile so the caller can skip the chart
    rather than emit a degenerate one-axis SVG.
    """

    count = len(profile)
    if count < 3:
        return None

    centre = size / 2
    radius = centre - padding

    ring_polys = [
        _to_points(_vertices(centre, centre, radius * (i + 1) / rings, count))
        for i in range(rings)
    ]

    outer = _vertices(centre, centre, radius, count)
    label_pts = _vertices(centre, centre, radius + 26, count)

    axes = []
    for i, entry in enumerate(profile):
        ox, oy = outer[i]
        lx, ly = label_pts[i]
        axes.append({
            "label": entry["skill"],
            "short": SHORT_LABELS.get(entry["skill"], entry["skill"]),
            "score": entry["score"],
            "plays": entry["plays"],
            # An axis nobody has played is dimmed: its point sits at the
            # centre, and without this the viewer reads "untrained" as
            # "bad at it".
            "empty": entry["plays"] == 0,
            "x": ox,
            "y": oy,
            "label_x": lx,
            # Nudge labels off the horizontal midline so they sit on the
            # spoke rather than crossing it.
            "label_y": round(ly + 4, 2),
            "anchor": _label_anchor(centre, lx),
        })

    def polygon_for(values):
        pts = []
        for i, value in enumerate(values):
            r = radius * max(0, min(100, value)) / 100
            vx, vy = _vertices(centre, centre, r, count)[i]
            pts.append((vx, vy))
        return pts

    data_pts = polygon_for([e["score"] for e in profile])
    measured = sum(1 for e in profile if e["plays"])

    result = {
        "size": size,
        # Labels sit outside the circle and are anchored outward, so the
        # drawing bleeds past the square the geometry is built in. The
        # viewBox is widened rather than the radar shrunk, which would
        # cost chart area to buy margin that is mostly empty anyway.
        "view_box": f"-30 0 {size + 60} {size}",
        "centre": centre,
        "radius": radius,
        "rings": ring_polys,
        "axes": axes,
        "points": _to_points(data_pts),
        "dots": [{"x": x, "y": y} for x, y in data_pts],
        "measured": measured,
        # Below three measured axes there is no polygon worth drawing --
        # one or two points collapse into a spike out of the centre,
        # which reads as a broken chart rather than as a sparse one. The
        # template falls back to the bare grid and a prompt, which is
        # both honest and deliberate-looking on a fresh install.
        "has_data": measured >= 3,
    }

    if compare and len(compare) == count:
        result["compare_points"] = _to_points(
            polygon_for([e["score"] for e in compare])
        )
        result["compare_has_data"] = sum(1 for e in compare if e["plays"]) >= 3

    return result
