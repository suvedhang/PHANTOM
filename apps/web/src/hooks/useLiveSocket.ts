import { useEffect, useRef, useState } from "react";

import { wsUrl } from "../api/config";
import type { WsMessage } from "../api/types";

export type SocketState = "connecting" | "open" | "closed";

/**
 * Live WebSocket subscription with exponential-backoff reconnect.
 *
 * The hub intentionally drops high-frequency `observation` frames under load
 * and closes slow clients; this client therefore treats reconnects as normal
 * and re-fetches durable state (events, status) over REST on reconnect.
 */
export function useLiveSocket(
  onMessage: (message: WsMessage) => void,
  options: { enabled?: boolean } = {},
): { state: SocketState; lastMessageAt: number | null; attempts: number } {
  const { enabled = true } = options;
  const [state, setState] = useState<SocketState>("closed");
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null);
  const [attempts, setAttempts] = useState(0);
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    if (!enabled) return;
    let socket: WebSocket | null = null;
    let closedByUs = false;
    let retry = 0;
    let timer: number | undefined;

    const connect = () => {
      setState("connecting");
      socket = new WebSocket(wsUrl());

      socket.onopen = () => {
        setState("open");
        setAttempts(retry);
        retry = 0;
      };

      socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data as string) as WsMessage;
          setLastMessageAt(Date.now());
          handlerRef.current(parsed);
        } catch {
          // Ignore malformed frames.
        }
      };

      socket.onclose = () => {
        setState("closed");
        if (closedByUs) return;
        retry += 1;
        setAttempts(retry);
        const delay = Math.min(15000, 500 * 2 ** Math.min(retry, 5));
        timer = window.setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();
    return () => {
      closedByUs = true;
      if (timer) window.clearTimeout(timer);
      socket?.close();
    };
  }, [enabled]);

  return { state, lastMessageAt, attempts };
}
