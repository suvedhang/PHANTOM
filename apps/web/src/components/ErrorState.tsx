import "./components.css";

export interface ErrorStateProps {
  error: unknown;
  title?: string;
  onRetry?: () => void;
}

function guidance(error: unknown): string {
  if (error && typeof error === "object" && "category" in error) {
    switch ((error as { category: string }).category) {
      case "offline":
        return "The API is unreachable. Start the backend and confirm VITE_API_BASE_URL points at it.";
      case "timeout":
        return "The API did not respond in time. Check System Health, then retry.";
      case "unauthorized":
        return "This action requires authorization that is not configured.";
      case "not_found":
        return "The requested record no longer exists.";
      case "validation":
        return "The request failed validation. Check the highlighted fields.";
      case "conflict":
        return "The action conflicts with the current state. Reload and try again.";
      case "server":
        return "The API returned a server error. See System Health for recent errors.";
      default:
        break;
    }
  }
  return "Something went wrong while loading this view.";
}

export function ErrorState({ error, title = "Unable to load", onRetry }: ErrorStateProps) {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return (
    <div className="error-state" role="alert">
      <div className="error-state-head">
        <span className="error-state-mark" aria-hidden="true">
          !
        </span>
        <div>
          <h3 className="error-state-title">{title}</h3>
          <p className="error-state-message">{message}</p>
        </div>
      </div>
      <p className="error-state-hint">{guidance(error)}</p>
      {onRetry && (
        <div className="error-state-actions">
          <button className="btn btn-secondary btn-sm" type="button" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
