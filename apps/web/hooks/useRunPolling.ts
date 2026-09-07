"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { api, ApiError } from "@/lib/api";
import type { components } from "@/lib/schema";

type RunDetail = components["schemas"]["RunDetail"];
type JobStatus = components["schemas"]["JobStatusResponse"];

interface UseRunPollingResult {
  run: RunDetail | null;
  job: JobStatus | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Polling hook matching Blueprint Section 16.2:
 * - Polls once per second while QUEUED or RUNNING.
 * - Stops on terminal state (SUCCEEDED or FAILED).
 * - Backs off to 5 seconds after 2 minutes (120s).
 * - Stateless across refresh: fetches latest state from backend on mount.
 */
export function useRunPolling(runId: string): UseRunPollingResult {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const startTimeRef = useRef<number>(Date.now());
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const isTerminalRef = useRef<boolean>(false);

  const fetchState = useCallback(async () => {
    try {
      // 1. Fetch Run details
      const runData = await api.getRun(runId);
      setRun(runData);

      // 2. Fetch background Job details (using runId fallback or jobId)
      try {
        const jobData = await api.getJob(runId);
        setJob(jobData);
      } catch {
        // Job record might not exist or completed earlier
      }

      if (runData.status === "SUCCEEDED" || runData.status === "FAILED") {
        isTerminalRef.current = true;
      }
      setError(null);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.problem.title);
      } else {
        setError((err as Error).message || "Failed to poll run state");
      }
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    startTimeRef.current = Date.now();
    isTerminalRef.current = false;
    setLoading(true);

    // Initial immediate fetch
    fetchState();

    function scheduleNextPoll() {
      if (isTerminalRef.current) return;

      const elapsedSec = (Date.now() - startTimeRef.current) / 1000;
      // Section 16.2: 1s interval while queued/running; backoff to 5s after 2 minutes (120s)
      const intervalMs = elapsedSec > 120 ? 5000 : 1000;

      timerRef.current = setTimeout(async () => {
        await fetchState();
        if (!isTerminalRef.current) {
          scheduleNextPoll();
        }
      }, intervalMs);
    }

    scheduleNextPoll();

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [runId, fetchState]);

  return { run, job, loading, error, refetch: fetchState };
}
