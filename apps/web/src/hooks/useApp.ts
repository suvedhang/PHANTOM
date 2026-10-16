import { useContext } from "react";

import { AppContext, type AppContextValue } from "../app/AppContext";

/** Access app-wide live status (source, pipeline, transport, socket). */
export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) {
    throw new Error("useApp must be used within an AppProvider.");
  }
  return value;
}
