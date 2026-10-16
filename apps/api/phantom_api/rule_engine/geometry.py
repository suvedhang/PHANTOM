"""Polygon and geometry helpers.

All geometry operates on normalized image coordinates in [0, 1]. These helpers
are pure functions and are unit-tested directly.
"""

from __future__ import annotations

import math

from ..schemas import Point, Polygon


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Return True if ``point`` is inside ``polygon``.

    Uses the even-odd (ray casting) rule. Points exactly on an edge are
    considered inside (documented behaviour, tested).
    """
    pts = polygon.points
    n = len(pts)
    if n < 3:
        return False

    x, y = point.x, point.y
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = pts[i].x, pts[i].y
        xj, yj = pts[j].x, pts[j].y
        # On-edge check (collinear and within segment bounds).
        if _on_segment(x, y, xi, yi, xj, yj):
            return True
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def _on_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> bool:
    cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
    if abs(cross) > 1e-9:
        return False
    within_x = min(x1, x2) - 1e-9 <= px <= max(x1, x2) + 1e-9
    within_y = min(y1, y2) - 1e-9 <= py <= max(y1, y2) + 1e-9
    return within_x and within_y


def polygon_centroid(polygon: Polygon) -> Point:
    pts = polygon.points
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i].x, pts[i].y
        x1, y1 = pts[(i + 1) % n].x, pts[(i + 1) % n].y
        cross = x0 * y1 - x1 * y0
        area2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area2) < 1e-12:
        # Degenerate: return mean of vertices.
        return Point(x=sum(p.x for p in pts) / n, y=sum(p.y for p in pts) / n)
    return Point(x=cx / (3 * area2), y=cy / (3 * area2))


def displacement(start: Point, end: Point) -> float:
    """Euclidean image-space displacement between two normalized points."""
    return math.hypot(end.x - start.x, end.y - start.y)


def bearing_degrees(start: Point, end: Point) -> float | None:
    """Image-space bearing in degrees, clockwise from +x axis.

    Returns None when start and end coincide. This is an image-space angle, not
    a compass heading, and must not be reported as physical direction.
    """
    dx = end.x - start.x
    dy = end.y - start.y
    if math.hypot(dx, dy) < 1e-9:
        return None
    angle = math.degrees(math.atan2(dy, dx)) % 360.0
    return angle


def angular_difference_degrees(a: float, b: float) -> float:
    """Smallest absolute difference between two angles in [0, 180]."""
    diff = abs((a - b) % 360.0)
    return min(diff, 360.0 - diff)


def bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    """Intersection-over-union for normalized boxes (x_min, y_min, x_max, y_max)."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    intersection = iw * ih
    if intersection <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0
