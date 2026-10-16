import { useState } from "react";

import { ApiError, api } from "../api/client";
import { Button } from "../components/Button";
import { useApp } from "../hooks/useApp";
import { useToast } from "../hooks/useToast";

export function RunControl() {
  const { status, refresh } = useApp();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const running = status?.pipeline.mode === "simulated" || status?.active_run_id !== null;
  const mode = status?.pipeline.mode ?? "disconnected";

  const start = async () => {
    setBusy(true);
    try {
      const result = await api.startRun("mock", 15);
      toast.ok("Simulated run started", result.message);
      refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not start the run.";
      toast.error("Failed to start run", message);
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await api.stopRun();
      toast.info("Run stopped");
      refresh();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not stop the run.";
      toast.error("Failed to stop run", message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="run-control">
      <span className="run-control-mode mono">{mode}</span>
      <Button
        size="sm"
        variant={running ? "danger" : "primary"}
        loading={busy}
        onClick={running ? stop : start}
      >
        {running ? "Stop" : "Start simulated run"}
      </Button>
    </div>
  );
}
