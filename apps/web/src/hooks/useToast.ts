import { useContext } from "react";

import { ToastContext, type ToastApi } from "../components/Toast";

/** Access the app-wide toast notification API. */
export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) {
    throw new Error("useToast must be used within a ToastProvider.");
  }
  return api;
}
