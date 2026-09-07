"use client";

import React, { useState, useEffect, useRef, use } from "react";
import Link from "next/link";
import {
  Play,
  Film,
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  Camera,
  Shield,
  FileCode2,
  ArrowRight,
  RefreshCw,
  Filter,
  Eye,
} from "lucide-react";
import { api, ProblemDetails } from "@/lib/api";
import { useRunPolling } from "@/hooks/useRunPolling";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { Badge, RiskBadge, VerdictBadge } from "@/components/ui/Badge";
import { StateWrapper, AsyncState } from "@/components/ui/StateWrapper";
import { Timeline } from "@/components/runs/Timeline";
import type { components } from "@/lib/schema";

type EventDetail = components["schemas"]["EventDetail"];
type VideoResponse = components["schemas"]["VideoResponse"];

interface RunPageProps {
  params: Promise<{ runId: string }>;
}

export default function RunDetailPage({ params }: RunPageProps) {
  const resolvedParams = use(params);
  const runId = resolvedParams.runId;

  // Real-time polling hook (Blueprint §16.2)
  const { run, job, loading: runLoading, error: runError, refetch } = useRunPolling(runId);

  // Video & Events state
  const [video, setVideo] = useState<VideoResponse | null>(null);
  const [events, setEvents] = useState<EventDetail[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsError, setEventsError] = useState<string | null>(null);

  // Playback & Selection
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<EventDetail | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Filters
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>("ALL");
  const [selectedTierFilter, setSelectedTierFilter] = useState<string>("ALL");
  const [selectedReviewFilter, setSelectedReviewFilter] = useState<string>("ALL");

  // Load video metadata once run is available
  useEffect(() => {
    if (!run?.video_id) return;
    api
      .getVideo(run.video_id)
      .then(setVideo)
      .catch(() => {
        // Fallback or ignore if video record lookup fails
      });
  }, [run?.video_id]);

  // Fetch events when run is SUCCEEDED
  useEffect(() => {
    if (run?.status !== "SUCCEEDED") return;

    let isMounted = true;
    setEventsLoading(true);
    api
      .getEvents({ run_id: runId, limit: 100 })
      .then((res) => {
        if (isMounted) {
          setEvents(res.items);
          if (res.items.length > 0 && !selectedEvent) {
            setSelectedEvent(res.items[0]);
          }
        }
      })
      .catch((err) => {
        if (isMounted) {
          setEventsError((err as Error).message || "Failed to load events");
        }
      })
      .finally(() => {
        if (isMounted) setEventsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [run?.status, runId]);

  // Video time update handler
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTimeMs(Math.round(videoRef.current.currentTime * 1000));
    }
  };

  const handleSeek = (timeMs: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = timeMs / 1000;
      setCurrentTimeMs(timeMs);
    }
  };

  // Filter events
  const filteredEvents = events.filter((e) => {
    if (selectedTypeFilter !== "ALL" && e.event_type !== selectedTypeFilter) return false;
    if (selectedTierFilter !== "ALL" && e.risk?.tier !== selectedTierFilter) return false;
    if (selectedReviewFilter !== "ALL") {
      const verdict = e.review?.verdict || "UNREVIEWED";
      if (verdict !== selectedReviewFilter) return false;
    }
    return true;
  });

  // Calculate overall async state
  let overallState: AsyncState = "loading";
  if (!runLoading) {
    if (runError && !run) {
      overallState = "error";
    } else if (run?.status === "SUCCEEDED" && events.length === 0 && !eventsLoading) {
      overallState = "success-empty";
    } else {
      overallState = "success-with-data";
    }
  }

  const durationMs = video?.duration_ms || (events.length > 0 ? Math.max(...events.map((e) => e.end_ms)) : 60000);

  return (
    <StateWrapper
      state={overallState}
      errorMessage={runError || "Unable to load run"}
      onRetry={refetch}
      emptyTitle="No Risk Events Detected"
      emptyMessage="Analysis completed cleanly. No policy violation or risk thresholds were exceeded."
    >
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Replay Banner per Section 16.2 */}
        {run?.mode === "REPLAY" && (
          <div className="p-3 rounded-lg border border-amber-800/80 bg-amber-950/40 text-amber-200 text-xs flex items-center gap-2">
            <Badge variant="warning">REPLAY MODE</Badge>
            <span>Replay mode — detections loaded from a previously generated artifact.</span>
          </div>
        )}

        {/* Header and Status Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-slate-100 font-mono">
                Run #{runId.slice(0, 8)}
              </h1>
              <Badge
                variant={
                  run?.status === "SUCCEEDED"
                    ? "success"
                    : run?.status === "RUNNING"
                    ? "medium"
                    : run?.status === "FAILED"
                    ? "critical"
                    : "neutral"
                }
              >
                {run?.status}
              </Badge>
              {run?.mode && (
                <Badge variant={run.mode === "LIVE" ? "success" : "warning"}>{run.mode}</Badge>
              )}
            </div>
            <div className="text-xs text-slate-400 mt-1 flex items-center gap-4 flex-wrap">
              <span>Video: {video?.original_name || run?.video_id.slice(0, 8)}</span>
              <span>Camera: {run?.camera_profile_id} (v{run?.camera_profile_version})</span>
              <span>Model: {run?.model_backend}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {run?.manifest_url && (
              <a
                href={api.getMediaUrl(runId)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex"
              >
                <Button variant="secondary" size="sm" className="flex items-center gap-1.5 text-xs">
                  <FileCode2 className="w-3.5 h-3.5" />
                  Manifest
                </Button>
              </a>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refetch()}
              className="text-xs flex items-center gap-1"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Processing Banner if QUEUED or RUNNING */}
        {(run?.status === "QUEUED" || run?.status === "RUNNING") && (
          <Card className="bg-blue-950/20 border-blue-900/60">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-blue-400 animate-spin" />
                  <div>
                    <h4 className="text-sm font-semibold text-blue-200">
                      Processing Surveillance Video: {job?.stage || "QUEUED"}
                    </h4>
                    <p className="text-xs text-blue-300/80">
                      Worker progress stage {job?.stage || "INITIALIZING"} · Attempt #{job?.attempt || 1}
                    </p>
                  </div>
                </div>
                <span className="text-sm font-mono font-bold text-blue-300">
                  {job?.progress ?? 0}%
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-blue-950">
                <div
                  className="bg-blue-500 h-full transition-all duration-300 ease-out"
                  style={{ width: `${job?.progress ?? 5}%` }}
                />
              </div>

              <div className="text-[11px] text-slate-400 flex items-center justify-between">
                <span>Polling every 1s (backs off to 5s after 2min)</span>
                <span>Page state is strictly restored from backend</span>
              </div>
            </div>
          </Card>
        )}

        {/* Failure Banner if FAILED */}
        {run?.status === "FAILED" && (
          <Alert variant="danger" title="Analysis Pipeline Failed">
            <div className="space-y-1">
              <p className="text-xs">
                {job?.error && typeof job.error === "object" && "detail" in job.error
                  ? String(job.error.detail)
                  : "The background analysis job encountered a terminal execution failure."}
              </p>
              {job?.error && typeof job.error === "object" && "code" in job.error && (
                <div className="font-mono text-[10px] text-rose-300">
                  Error Code: {String(job.error.code)}
                </div>
              )}
            </div>
          </Alert>
        )}

        {/* Main Workspace: Video Player & Event Side Panel */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Cols: Video Player & Scrubber */}
          <div className="lg:col-span-2 space-y-4">
            <div className="relative rounded-xl overflow-hidden bg-black border border-slate-800 shadow-2xl aspect-video flex items-center justify-center">
              {run?.status === "SUCCEEDED" ? (
                <video
                  ref={videoRef}
                  controls
                  playsInline
                  onTimeUpdate={handleTimeUpdate}
                  className="w-full h-full object-contain"
                  src={api.getMediaUrl(runId)}
                >
                  Your browser does not support HTML5 video streaming.
                </video>
              ) : (
                <div className="flex flex-col items-center gap-2 text-slate-500">
                  <Film className="w-12 h-12 stroke-[1.5]" />
                  <span className="text-xs">
                    {run?.status === "FAILED" ? "Video unavailable" : "Awaiting normalized video stream..."}
                  </span>
                </div>
              )}
            </div>

            {/* Interactive Timeline Scrubbing Bar */}
            {run?.status === "SUCCEEDED" && (
              <Timeline
                durationMs={durationMs}
                currentTimeMs={currentTimeMs}
                events={filteredEvents}
                selectedEventId={selectedEvent?.id || null}
                onSelectEvent={setSelectedEvent}
                onSeek={handleSeek}
              />
            )}

            {/* Mandatory Disclaimers Banner (Blueprint §16.2) */}
            <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/40 text-xs text-slate-400 space-y-1">
              <div className="font-semibold text-slate-300">Mandatory Operational Context:</div>
              <ul className="list-disc list-inside space-y-0.5 text-slate-400 text-[11px]">
                <li>Risk event, not confirmed damage.</li>
                <li>Evidence quality is not probability.</li>
                <li>All automated findings are subject to human review and verification.</li>
              </ul>
            </div>
          </div>

          {/* Right Col: Filter Chips and Event List */}
          <div className="space-y-4">
            {/* Filter Chips */}
            <Card>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-200">
                  <span className="flex items-center gap-1.5">
                    <Filter className="w-3.5 h-3.5 text-slate-400" />
                    Filters ({filteredEvents.length} of {events.length})
                  </span>
                  {(selectedTypeFilter !== "ALL" ||
                    selectedTierFilter !== "ALL" ||
                    selectedReviewFilter !== "ALL") && (
                    <button
                      onClick={() => {
                        setSelectedTypeFilter("ALL");
                        setSelectedTierFilter("ALL");
                        setSelectedReviewFilter("ALL");
                      }}
                      className="text-[11px] text-blue-400 hover:underline cursor-pointer"
                    >
                      Reset
                    </button>
                  )}
                </div>

                {/* Risk Tier Chips */}
                <div>
                  <div className="text-[10px] uppercase font-bold text-slate-500 mb-1.5 tracking-wider">
                    Risk Tier
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((t) => (
                      <button
                        key={t}
                        onClick={() => setSelectedTierFilter(t)}
                        className={`px-2 py-0.5 rounded text-xs font-medium cursor-pointer transition-colors ${
                          selectedTierFilter === t
                            ? "bg-blue-600 text-white"
                            : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Review Verdict Chips */}
                <div>
                  <div className="text-[10px] uppercase font-bold text-slate-500 mb-1.5 tracking-wider">
                    Review Status
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {["ALL", "CONFIRMED_RISK", "REJECTED", "UNCERTAIN", "UNREVIEWED"].map((v) => (
                      <button
                        key={v}
                        onClick={() => setSelectedReviewFilter(v)}
                        className={`px-2 py-0.5 rounded text-xs font-medium cursor-pointer transition-colors ${
                          selectedReviewFilter === v
                            ? "bg-blue-600 text-white"
                            : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                        }`}
                      >
                        {v === "CONFIRMED_RISK"
                          ? "Confirmed"
                          : v === "REJECTED"
                          ? "Rejected"
                          : v === "UNCERTAIN"
                          ? "Uncertain"
                          : v === "UNREVIEWED"
                          ? "Unreviewed"
                          : "All"}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>

            {/* Event List */}
            <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
              {filteredEvents.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">
                  No events match the selected filters.
                </div>
              ) : (
                filteredEvents.map((evt) => {
                  const isSelected = selectedEvent?.id === evt.id;
                  const startSec = (evt.start_ms / 1000).toFixed(1);
                  const endSec = (evt.end_ms / 1000).toFixed(1);

                  return (
                    <div
                      key={evt.id}
                      onClick={() => {
                        setSelectedEvent(evt);
                        handleSeek(evt.start_ms);
                      }}
                      className={`p-3 rounded-lg border transition-all cursor-pointer ${
                        isSelected
                          ? "bg-slate-800/90 border-blue-500 shadow-md ring-1 ring-blue-500/50"
                          : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <span className="font-semibold text-xs text-slate-200">
                          {evt.event_type.replace(/_/g, " ")}
                        </span>
                        <RiskBadge tier={evt.risk?.tier || "LOW"} />
                      </div>

                      <div className="text-[11px] text-slate-400 flex items-center justify-between">
                        <span className="font-mono text-blue-300">
                          {startSec}s - {endSec}s
                        </span>
                        <span>Score: {evt.risk?.score}</span>
                      </div>

                      <div className="mt-2 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px]">
                        <div className="flex items-center gap-1.5">
                          {evt.review ? (
                            <VerdictBadge verdict={evt.review.verdict} />
                          ) : (
                            <Badge variant="neutral">Unreviewed</Badge>
                          )}
                        </div>

                        <Link
                          href={`/events/${evt.id}`}
                          className="text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Details
                          <ArrowRight className="w-3 h-3" />
                        </Link>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </StateWrapper>
  );
}
