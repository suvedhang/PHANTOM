import type { Polygon } from "../api/types";

/** Returns the center of a polygon (mean of its vertices). */
export function polygonCenter(polygon: Polygon): { x: number; y: number } {
  const points = polygon.points;
  if (points.length === 0) return { x: 0.5, y: 0.5 };
  const sum = points.reduce((acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }), {
    x: 0,
    y: 0,
  });
  return { x: sum.x / points.length, y: sum.y / points.length };
}

/**
 * Ray-casting point-in-polygon test in the normalized [0,1] coordinate space.
 * Mirrors the backend behavior in `rule_engine/geometry.py`.
 */
export function pointInPolygon(
  point: { x: number; y: number },
  polygon: Polygon,
): boolean {
  const points = polygon.points;
  const n = points.length;
  if (n < 3) return false;

  let inside = false;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const a = points[i]!;
    const b = points[j]!;
    const intersect =
      a.y > point.y !== b.y > point.y &&
      point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x;
    if (intersect) inside = !inside;
  }
  return inside;
}
