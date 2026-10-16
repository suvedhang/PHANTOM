import "./components.css";

export function Spinner({ size = 16, label }: { size?: number; label?: string }) {
  return (
    <span
      className="spinner"
      style={{ width: size, height: size }}
      role="status"
      aria-label={label ?? "Loading"}
    />
  );
}

export function Skeleton({
  height = 16,
  width = "100%",
  radius,
}: {
  height?: number | string;
  width?: number | string;
  radius?: number;
}) {
  return (
    <span
      className="skeleton"
      aria-hidden="true"
      style={{ height, width, borderRadius: radius }}
    />
  );
}

/** Loading placeholder for a panel with a title and rows. */
export function LoadingPanel({ rows = 4, title = true }: { rows?: number; title?: boolean }) {
  return (
    <div className="loading-panel" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading content</span>
      {title && <Skeleton height={18} width="40%" />}
      <div className="stack" style={{ marginTop: 12, gap: 10 }}>
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} height={12} width={`${90 - index * 8}%`} />
        ))}
      </div>
    </div>
  );
}
