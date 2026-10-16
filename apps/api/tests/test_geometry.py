"""Unit tests for geometry helpers."""

from __future__ import annotations

import pytest

from phantom_api.rule_engine.geometry import (
    angular_difference_degrees,
    bearing_degrees,
    bbox_iou,
    displacement,
    point_in_polygon,
    polygon_centroid,
)
from phantom_api.schemas import Point, Polygon


def square() -> Polygon:
    return Polygon(
        points=[
            Point(x=0.2, y=0.2),
            Point(x=0.8, y=0.2),
            Point(x=0.8, y=0.8),
            Point(x=0.2, y=0.8),
        ]
    )


def test_point_clearly_inside() -> None:
    assert point_in_polygon(Point(x=0.5, y=0.5), square()) is True


def test_point_clearly_outside() -> None:
    assert point_in_polygon(Point(x=0.1, y=0.1), square()) is False


def test_point_on_edge_is_inside() -> None:
    assert point_in_polygon(Point(x=0.2, y=0.5), square()) is True


def test_point_on_vertex_is_inside() -> None:
    assert point_in_polygon(Point(x=0.2, y=0.2), square()) is True


def test_degenerate_polygon_rejected() -> None:
    with pytest.raises(ValueError):
        Polygon(points=[Point(x=0.1, y=0.1), Point(x=0.1, y=0.1), Point(x=0.1, y=0.1)])


def test_polygon_needs_three_points() -> None:
    with pytest.raises(ValueError):
        Polygon(points=[Point(x=0.1, y=0.1), Point(x=0.2, y=0.2)])


def test_centroid_of_square() -> None:
    c = polygon_centroid(square())
    assert c.x == pytest.approx(0.5)
    assert c.y == pytest.approx(0.5)


def test_displacement() -> None:
    assert displacement(Point(x=0.0, y=0.0), Point(x=0.3, y=0.4)) == pytest.approx(0.5)


def test_bearing_east() -> None:
    assert bearing_degrees(Point(x=0.1, y=0.5), Point(x=0.9, y=0.5)) == pytest.approx(0.0)


def test_bearing_west() -> None:
    assert bearing_degrees(Point(x=0.9, y=0.5), Point(x=0.1, y=0.5)) == pytest.approx(180.0)


def test_bearing_insufficient_history_is_none() -> None:
    assert bearing_degrees(Point(x=0.5, y=0.5), Point(x=0.5, y=0.5)) is None


def test_angular_difference_wraps() -> None:
    assert angular_difference_degrees(350.0, 10.0) == pytest.approx(20.0)
    assert angular_difference_degrees(0.0, 180.0) == pytest.approx(180.0)


def test_bbox_iou_identical() -> None:
    assert bbox_iou((0.1, 0.1, 0.5, 0.5), (0.1, 0.1, 0.5, 0.5)) == pytest.approx(1.0)


def test_bbox_iou_disjoint() -> None:
    assert bbox_iou((0.0, 0.0, 0.1, 0.1), (0.5, 0.5, 0.6, 0.6)) == 0.0
