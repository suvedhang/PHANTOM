import {
  createContext,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import "./components.css";

export type ToastTone = "ok" | "warn" | "danger" | "info";

export interface Toast {
  id: number;
  tone: ToastTone;
  title: string;
  message?: string;
  sticky?: boolean;
}

export interface ToastApi {
  push: (toast: Omit<Toast, "id">) => void;
  ok: (title: string, message?: string) => void;
  warn: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const ToastContext = createContext<ToastApi | null>(null);

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((toast: Omit<Toast, "id">) => {
    const id = nextId++;
    setToasts((current) => [...current, { ...toast, id }]);
    if (!toast.sticky) {
      window.setTimeout(() => {
        setToasts((current) => current.filter((t) => t.id !== id));
      }, 5000);
    }
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      push,
      ok: (title, message) => push({ tone: "ok", title, message }),
      warn: (title, message) => push({ tone: "warn", title, message }),
      error: (title, message) => push({ tone: "danger", title, message }),
      info: (title, message) => push({ tone: "info", title, message }),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-region" role="region" aria-label="Notifications">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone}`} role="status">
            <div className="toast-body">
              <span className="toast-title">{toast.title}</span>
              {toast.message && <span className="toast-message">{toast.message}</span>}
            </div>
            <button
              type="button"
              className="toast-close"
              aria-label="Dismiss notification"
              onClick={() =>
                setToasts((current) => current.filter((t) => t.id !== toast.id))
              }
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
