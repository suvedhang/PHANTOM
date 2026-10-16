import type { NormalizedEntity, Point, RegionModel } from "../api/types";

import "./components.css";

export interface SceneOverlayProps {
  entities: NormalizedEntity[];
  tracks: Array<{ track_id: string; class_label: string; recent_positions: Point[] }>;
  regions: RegionModel[];
  showTrails: boolean;
  highlightedTrackIds?: Set<string>;
}

/**
 * Renders normalized scene data as an overlay in the closed [0,1] coordinate
 * space. The SVG viewBox is fixed to 0..1 with preserveAspectRatio="none" so
 * normalized coordinates map directly onto the video/poster area regardless of
 * its pixel size. Overlays are stroke-only so they never obscure evidence.
 */
export function SceneOverlay({
  entities,
  tracks,
  regions,
  showTrails,
  highlightedTrackIds,
}: SceneOverlayProps) {
  return (
    <svg
      className="scene-overlay"
      viewBox="0 0 1 1"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {regions.map((region) => {
        const points = region.polygon.points
          .map((p) => `${p.x},${p.y}`)
          .join(" ");
        return (
          <polygon
            key={region.region_id}
            points={points}
            className="overlay-region"
            vectorEffect="non-scaling-stroke"
          />
        );
      })}

      {showTrails &&
        tracks.map((track) => {
          if (track.recent_positions.length < 2) return null;
          const points = track.recent_positions
            .map((p) => `${p.x},${p.y}`)
            .join(" ");
          return (
            <polyline
              key={`trail-${track.track_id}`}
              points={points}
              className="overlay-trail"
              vectorEffect="non-scaling-stroke"
            />
          );
        })}

      {entities.map((entity, index) => {
        if (!entity.bbox) return null;
        const { x_min, y_min, x_max, y_max } = entity.bbox;
        const width = Math.max(0.001, x_max - x_min);
        const height = Math.max(0.001, y_max - y_min);
        const highlighted = entity.track_id
          ? highlightedTrackIds?.has(entity.track_id)
          : false;
        return (
          <g key={entity.track_id ?? `entity-${index}`}>
            <rect
              x={x_min}
              y={y_min}
              width={width}
              height={height}
              className={`overlay-box ${highlighted ? "overlay-box-highlight" : ""}`}
              vectorEffect="non-scaling-stroke"
            />
            <text x={x_min} y={Math.max(0.02, y_min - 0.01)} className="overlay-label">
              {entity.class_label}
              {entity.track_id ? ` · ${entity.track_id}` : ""}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
