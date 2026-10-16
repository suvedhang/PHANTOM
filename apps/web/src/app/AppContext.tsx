import {
  createContext,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, asObservationFrame } from "../api/client";
import type { ObservationFrame, PipelineInfo, SystemStatus, WsMessage } from "../api/types";
import { useApi } from "../hooks/useApi";
import { useLiveSocket, type SocketState } from "../hooks/useLiveSocket";

export interface AppContextValue {
  status: SystemStatus | null;
  error: unknown;
  loading: boolean;
  refresh: () => void;
  socketState: SocketState;
  /** Increments whenever a durable event is created or updated. */
  eventsRevision: number;
  /** Latest live observation frame, if a simulated/live run is streaming. */
  latestFrame: ObservationFrame | null;
  /** Live counts of observation/event frames received this session. */
  liveCounters: { observations: number; events: number; lastHeartbeat: number | null };
}

// eslint-disable-next-line react-refresh/only-export-components
export const AppContext = createContext<AppContextValue | null>(null);

const POLL_MS = 5000;

export function AppProvider({ children }: { children: ReactNode }) {
  const statusState = useApi<SystemStatus>(() => api.systemStatusDetail(), [], {
    pollMs: POLL_MS,
  });
  const [liveStatus, setLiveStatus] = useState<PipelineInfo | null>(null);
  const [eventsRevision, setEventsRevision] = useState(0);
  const [observations, setObservations] = useState(0);
  const [events, setEvents] = useState(0);
  const [lastHeartbeat, setLastHeartbeat] = useState<number | null>(null);
  const [latestFrame, setLatestFrame] = useState<ObservationFrame | null>(null);

  const onMessage = useCallback((message: WsMessage) => {
    switch (message.type) {
      case "run_status":
        setLiveStatus(message.payload as PipelineInfo);
        break;
      case "event_created":
      case "event_updated":
        setEvents((n) => n + 1);
        setEventsRevision((n) => n + 1);
        break;
      case "observation": {
        const frame = asObservationFrame(message.payload);
        if (frame) setLatestFrame(frame);
        setObservations((n) => n + 1);
        break;
      }
      case "heartbeat":
        setLastHeartbeat(Date.now());
        break;
      default:
        break;
    }
  }, []);

  const { state: socketState } = useLiveSocket(onMessage);

  const status = useMemo<SystemStatus | null>(() => {
    if (!statusState.data) return null;
    if (liveStatus && liveStatus.mode !== "disconnected") {
      return { ...statusState.data, pipeline: liveStatus };
    }
    return statusState.data;
  }, [statusState.data, liveStatus]);

  const value = useMemo<AppContextValue>(
    () => ({
      status,
      error: statusState.error,
      loading: statusState.loading,
      refresh: statusState.reload,
      socketState,
      eventsRevision,
      latestFrame,
      liveCounters: { observations, events, lastHeartbeat },
    }),
    [
      status,
      statusState.error,
      statusState.loading,
      statusState.reload,
      socketState,
      eventsRevision,
      latestFrame,
      observations,
      events,
      lastHeartbeat,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
