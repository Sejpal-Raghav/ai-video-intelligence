"use client";

import React, { useState, useEffect, use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ShieldAlert,
  Clock,
  Crosshair,
  FileCheck2,
  UserCheck,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Send,
  Film,
  Activity,
  Layers,
  Sparkles,
} from "lucide-react";
import { api, ApiError, ProblemDetails } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { Badge, RiskBadge, VerdictBadge } from "@/components/ui/Badge";
import { StateWrapper, AsyncState } from "@/components/ui/StateWrapper";
import type { components } from "@/lib/schema";

type EventDetail = components["schemas"]["EventDetail"];
type ReviewResponse = components["schemas"]["ReviewResponse"];

interface EventPageProps {
  params: Promise<{ eventId: string }>;
}

function formatTimecode(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const millis = ms % 1000;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(
    millis
  ).padStart(3, "0")}`;
}

export default function EventDetailPage({ params }: EventPageProps) {
  const resolvedParams = use(params);
  const eventId = resolvedParams.eventId;

  const [event, setEvent] = useState<EventDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Review Form State
  const [verdict, setVerdict] = useState<"CONFIRMED_RISK" | "REJECTED" | "UNCERTAIN">(
    "CONFIRMED_RISK"
  );
  const [reviewerName, setReviewerName] = useState("Demo Reviewer");
  const [note, setNote] = useState("");
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  // Accordion toggle
  const [traceOpen, setTraceOpen] = useState(true);
  const [factsOpen, setFactsOpen] = useState(true);

  const fetchEvent = async () => {
    try {
      setLoading(true);
      const data = await api.getEvent(eventId);
      setEvent(data);
      if (data.review) {
        setVerdict(data.review.verdict);
      }
      setError(null);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.problem.title);
      } else {
        setError((err as Error).message || "Failed to load event details.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvent();
  }, [eventId]);

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reviewerName.trim()) {
      setReviewError("Reviewer name is required.");
      return;
    }

    setSubmittingReview(true);
    setReviewSuccess(null);
    setReviewError(null);

    try {
      const createdReview = await api.createReview(eventId, {
        verdict,
        reviewer_name: reviewerName.trim(),
        note: note.trim(),
      });

      // Update local event review state
      if (event) {
        setEvent({
          ...event,
          review: createdReview,
        });
      }

      setReviewSuccess(
        `Review revision #${createdReview.revision} recorded successfully.`
      );
      setNote("");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.problem.code === "REVIEW_CONFLICT") {
          setReviewError("A concurrent review was recorded. Please refresh and retry.");
        } else {
          setReviewError(err.problem.detail || err.problem.title);
        }
      } else {
        setReviewError((err as Error).message || "Failed to submit review.");
      }
    } finally {
      setSubmittingReview(false);
    }
  };

  let state: AsyncState = "loading";
  if (!loading) {
    if (error || !event) {
      state = "error";
    } else {
      state = "success-with-data";
    }
  }

  const mediaClipUrl = event?.media?.clip_id
    ? api.getMediaUrl(event.media.clip_id)
    : event?.run_id
    ? api.getMediaUrl(event.run_id)
    : null;

  const mediaThumbnailUrl = event?.media?.thumbnail_id
    ? api.getMediaUrl(event.media.thumbnail_id)
    : null;

  return (
    <StateWrapper
      state={state}
      errorMessage={error || "Event not found"}
      onRetry={fetchEvent}
    >
      {event && (
        <div className="max-w-6xl mx-auto space-y-6">
          {/* Breadcrumb / Back Link */}
          <div className="flex items-center justify-between">
            <Link
              href={`/runs/${event.run_id}`}
              className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Run #{event.run_id.slice(0, 8)}
            </Link>

            <span className="text-xs font-mono text-slate-500">ID: {event.id}</span>
          </div>

          {/* Header Card */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-xl border border-slate-800 bg-slate-900/60 shadow-lg">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold text-slate-100">
                  {event.event_type.replace(/_/g, " ")}
                </h1>
                <RiskBadge tier={event.risk?.tier || "LOW"} />
                {event.review ? (
                  <VerdictBadge verdict={event.review.verdict} />
                ) : (
                  <Badge variant="neutral">Unreviewed</Badge>
                )}
              </div>
              <p className="text-xs text-slate-400 leading-relaxed max-w-2xl">
                {event.explanation}
              </p>
            </div>

            <div className="flex items-center gap-4 bg-slate-950/60 p-3 rounded-lg border border-slate-800 font-mono text-xs">
              <div>
                <div className="text-[10px] text-slate-500 uppercase">Risk Score</div>
                <div className="text-base font-bold text-slate-200">{event.risk?.score}</div>
              </div>
              <div className="border-l border-slate-800 pl-4">
                <div className="text-[10px] text-slate-500 uppercase">Evidence Quality</div>
                <div className="text-base font-bold text-blue-400">
                  {(event.evidence_quality * 100).toFixed(0)}%
                </div>
              </div>
              <div className="border-l border-slate-800 pl-4">
                <div className="text-[10px] text-slate-500 uppercase">Primary Track</div>
                <div className="text-base font-bold text-slate-200">#{event.primary_track_id}</div>
              </div>
            </div>
          </div>

          {/* Mandatory Disclaimers per Blueprint §16.2 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/40 text-slate-400 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
              <span>Risk event, not confirmed damage.</span>
            </div>
            <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/40 text-slate-400 flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-400 shrink-0" />
              <span>Evidence quality is not probability.</span>
            </div>
          </div>

          {/* Workspace: Left = Evidence Video & Thumbnails, Right = Review & Facts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 2 Cols: Media Player & Decision Trace */}
            <div className="lg:col-span-2 space-y-6">
              {/* Evidence Clip Player */}
              <Card>
                <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                  <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                    <Film className="w-4 h-4 text-blue-400" />
                    Evidence Clip ({formatTimecode(event.start_ms)} – {formatTimecode(event.end_ms)})
                  </h3>
                  <Badge variant="neutral">
                    {((event.end_ms - event.start_ms) / 1000).toFixed(1)}s window
                  </Badge>
                </div>

                <div className="relative rounded-lg overflow-hidden bg-black border border-slate-800 aspect-video flex items-center justify-center">
                  {mediaClipUrl ? (
                    <video
                      controls
                      playsInline
                      className="w-full h-full object-contain"
                      src={mediaClipUrl}
                    >
                      Your browser does not support HTML5 video streaming.
                    </video>
                  ) : (
                    <div className="text-xs text-slate-500">Evidence clip not found</div>
                  )}
                </div>

                {mediaThumbnailUrl && (
                  <div className="mt-4 pt-4 border-t border-slate-800/80">
                    <div className="text-xs font-semibold text-slate-400 mb-2">
                      Keyframe Impact Thumbnail
                    </div>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={mediaThumbnailUrl}
                      alt="Event impact keyframe"
                      className="w-48 h-auto rounded border border-slate-800"
                    />
                  </div>
                )}
              </Card>

              {/* Deterministic Facts Breakdown */}
              <Card>
                <div
                  onClick={() => setFactsOpen(!factsOpen)}
                  className="flex items-center justify-between cursor-pointer select-none"
                >
                  <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-amber-400" />
                    Deterministic Kinematic & Spatial Facts
                  </h3>
                  {factsOpen ? (
                    <ChevronUp className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  )}
                </div>

                {factsOpen && (
                  <div className="mt-4 pt-3 border-t border-slate-800/80">
                    {Object.keys(event.facts).length === 0 ? (
                      <p className="text-xs text-slate-500">No raw kinematic facts available.</p>
                    ) : (
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        {Object.entries(event.facts).map(([key, val]) => (
                          <div
                            key={key}
                            className="p-2.5 rounded-lg border border-slate-800/80 bg-slate-950/40"
                          >
                            <div className="text-[10px] uppercase font-mono text-slate-400 truncate">
                              {key.replace(/_/g, " ")}
                            </div>
                            <div className="text-xs font-mono font-semibold text-slate-200 mt-0.5 truncate">
                              {typeof val === "number" ? val.toFixed(3) : String(val)}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </Card>

              {/* Decision Trace Accordion */}
              <Card>
                <div
                  onClick={() => setTraceOpen(!traceOpen)}
                  className="flex items-center justify-between cursor-pointer select-none"
                >
                  <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                    <Layers className="w-4 h-4 text-blue-400" />
                    Proof-Carrying Decision Trace (v1)
                  </h3>
                  {traceOpen ? (
                    <ChevronUp className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  )}
                </div>

                {traceOpen && (
                  <div className="mt-4 pt-3 border-t border-slate-800/80 space-y-3">
                    <p className="text-xs text-slate-400">
                      Evaluated rule predicates, physical thresholds, and track verification status.
                    </p>
                    <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
                      <pre className="text-[11px] leading-relaxed">
                        {JSON.stringify(
                          {
                            event_id: event.id,
                            event_type: event.event_type,
                            primary_track: event.primary_track_id,
                            verification_status: event.verification_status,
                            risk: event.risk,
                            evidence_quality: event.evidence_quality,
                            facts: event.facts,
                          },
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  </div>
                )}
              </Card>
            </div>

            {/* Right Col: Human Review Form */}
            <div className="space-y-6">
              {/* Latest Review Display */}
              <Card>
                <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-3">
                  <UserCheck className="w-4 h-4 text-emerald-400" />
                  Human Review Record
                </h3>

                {event.review ? (
                  <div className="space-y-3 p-3 rounded-lg bg-slate-950/50 border border-slate-800 text-xs">
                    <div className="flex items-center justify-between">
                      <VerdictBadge verdict={event.review.verdict} />
                      <span className="text-[10px] font-mono text-slate-500">
                        Revision #{event.review.revision}
                      </span>
                    </div>

                    {event.review.note && (
                      <p className="text-slate-300 italic bg-slate-900/50 p-2 rounded border border-slate-800">
                        &ldquo;{event.review.note}&rdquo;
                      </p>
                    )}

                    <div className="text-[10px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-800/60">
                      <span>Reviewer: {event.review.reviewer_name}</span>
                      <span>{new Date(event.review.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-lg border border-dashed border-slate-800 text-center text-xs text-slate-500">
                    This automated risk finding has not yet received human review.
                  </div>
                )}
              </Card>

              {/* Append-Only Review Submission Form */}
              <Card>
                <h3 className="text-sm font-semibold text-slate-200 mb-1">
                  Append Review Revision
                </h3>
                <p className="text-[11px] text-slate-400 mb-4">
                  Append-only review per Section 15.2. Prior revisions are permanently preserved.
                </p>

                {reviewSuccess && (
                  <Alert variant="success" title="Review Appended" className="mb-4">
                    {reviewSuccess}
                  </Alert>
                )}

                {reviewError && (
                  <Alert variant="danger" title="Review Failed" className="mb-4">
                    {reviewError}
                  </Alert>
                )}

                <form onSubmit={handleReviewSubmit} className="space-y-4">
                  {/* Verdict Selector */}
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-2">
                      Review Verdict (Non-punitive vocabulary)
                    </label>
                    <div className="space-y-2">
                      {[
                        {
                          val: "CONFIRMED_RISK",
                          label: "Human-confirmed risk",
                          desc: "Concur that handling poses package or safety risk.",
                        },
                        {
                          val: "REJECTED",
                          label: "Rejected",
                          desc: "False detection or benign compliant handling.",
                        },
                        {
                          val: "UNCERTAIN",
                          label: "Uncertain",
                          desc: "Occlusion or camera angle prevents clear assessment.",
                        },
                      ].map((item) => (
                        <label
                          key={item.val}
                          className={`flex items-start gap-2.5 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                            verdict === item.val
                              ? "bg-blue-950/40 border-blue-500 text-blue-200"
                              : "bg-slate-900/40 border-slate-800 text-slate-400 hover:border-slate-700"
                          }`}
                        >
                          <input
                            type="radio"
                            name="verdict"
                            value={item.val}
                            checked={verdict === item.val}
                            onChange={() =>
                              setVerdict(item.val as "CONFIRMED_RISK" | "REJECTED" | "UNCERTAIN")
                            }
                            className="mt-0.5 h-3.5 w-3.5 text-blue-600 bg-slate-800 border-slate-700"
                          />
                          <div>
                            <div className="text-xs font-semibold text-slate-200">{item.label}</div>
                            <div className="text-[10px] text-slate-400">{item.desc}</div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Reviewer Name */}
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Reviewer Name
                    </label>
                    <input
                      type="text"
                      value={reviewerName}
                      onChange={(e) => setReviewerName(e.target.value)}
                      placeholder="e.g. Quality Auditor"
                      required
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  {/* Notes */}
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Observations & Operational Notes
                    </label>
                    <textarea
                      rows={3}
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="Visible uncontrolled impact; inspect package before dispatch."
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    disabled={submittingReview || !reviewerName.trim()}
                    className="w-full flex items-center justify-center gap-2"
                  >
                    <Send className="w-3.5 h-3.5" />
                    {submittingReview ? "Recording Revision..." : "Append Review Revision"}
                  </Button>
                </form>
              </Card>
            </div>
          </div>
        </div>
      )}
    </StateWrapper>
  );
}
