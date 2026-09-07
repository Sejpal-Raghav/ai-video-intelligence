"use client";

import React, { useRef } from "react";
import type { components } from "@/lib/schema";

type EventDetail = components["schemas"]["EventDetail"];

interface TimelineProps {
  durationMs: number;
  currentTimeMs: number;
  events: EventDetail[];
  selectedEventId: string | null;
  onSelectEvent: (event: EventDetail) => void;
  onSeek: (timeMs: number) => void;
}

function formatTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const tenths = Math.floor((ms % 1000) / 100);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${tenths}`;
}

const TIER_COLORS: Record<string, { bg: string; border: string; glow: string }> = {
  CRITICAL: {
    bg: "bg-rose-500",
    border: "border-rose-400",
    glow: "shadow-[0_0_8px_rgba(244,63,94,0.6)]",
  },
  HIGH: {
    bg: "bg-orange-500",
    border: "border-orange-400",
    glow: "shadow-[0_0_8px_rgba(249,115,22,0.6)]",
  },
  MEDIUM: {
    bg: "bg-amber-500",
    border: "border-amber-400",
    glow: "shadow-[0_0_8px_rgba(245,158,11,0.5)]",
  },
  LOW: {
    bg: "bg-blue-500",
    border: "border-blue-400",
    glow: "shadow-[0_0_8px_rgba(59,130,246,0.5)]",
  },
};

export function Timeline({
  durationMs,
  currentTimeMs,
  events,
  selectedEventId,
  onSelectEvent,
  onSeek,
}: TimelineProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const effectiveDuration = Math.max(durationMs, 1000);

  const handleTrackClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    const clickRatio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    onSeek(Math.round(clickRatio * effectiveDuration));
  };

  const playheadPercent = Math.min(100, Math.max(0, (currentTimeMs / effectiveDuration) * 100));

  // Time grid markers (every 10s, 30s, or 60s based on duration)
  const markerStepMs = effectiveDuration > 120000 ? 30000 : effectiveDuration > 30000 ? 10000 : 5000;
  const markers = [];
  for (let t = 0; t <= effectiveDuration; t += markerStepMs) {
    markers.push(t);
  }

  return (
    <div className="space-y-2 select-none">
      {/* Time Display Header */}
      <div className="flex items-center justify-between text-xs font-mono text-slate-400 px-1">
        <span className="text-blue-400 font-semibold">{formatTime(currentTimeMs)}</span>
        <span>{formatTime(effectiveDuration)}</span>
      </div>

      {/* Interactive Timeline Track */}
      <div
        ref={trackRef}
        onClick={handleTrackClick}
        className="relative h-12 bg-slate-900 border border-slate-800 rounded-lg cursor-pointer overflow-hidden group shadow-inner"
        role="slider"
        aria-valuemin={0}
        aria-valuemax={effectiveDuration}
        aria-valuenow={currentTimeMs}
        aria-label="Video Event Timeline"
      >
        {/* Subtle grid ticks */}
        {markers.map((markerMs) => {
          const leftPct = (markerMs / effectiveDuration) * 100;
          return (
            <div
              key={markerMs}
              style={{ left: `${leftPct}%` }}
              className="absolute top-0 bottom-0 border-l border-slate-800/80 pointer-events-none"
            >
              <span className="absolute bottom-1 left-1 text-[9px] font-mono text-slate-600">
                {formatTime(markerMs).split(".")[0]}
              </span>
            </div>
          );
        })}

        {/* Event Intervals */}
        {events.map((event) => {
          const leftPct = Math.max(0, (event.start_ms / effectiveDuration) * 100);
          const widthPct = Math.max(
            1.5,
            Math.min(100 - leftPct, ((event.end_ms - event.start_ms) / effectiveDuration) * 100)
          );
          const tier = event.risk?.tier || "LOW";
          const isSelected = event.id === selectedEventId;
          const colors = TIER_COLORS[tier] || TIER_COLORS.LOW;

          return (
            <button
              key={event.id}
              type="button"
              style={{
                left: `${leftPct}%`,
                width: `${widthPct}%`,
              }}
              onClick={(e) => {
                e.stopPropagation();
                onSelectEvent(event);
                onSeek(event.start_ms);
              }}
              className={`absolute top-2 bottom-2 rounded-sm border transition-all z-10 cursor-pointer ${
                colors.bg
              } ${colors.border} ${isSelected ? `${colors.glow} ring-2 ring-white scale-y-110 z-20` : "opacity-85 hover:opacity-100 hover:scale-y-105"}`}
              title={`${event.event_type} (${tier}): ${formatTime(event.start_ms)} - ${formatTime(
                event.end_ms
              )}`}
            />
          );
        })}

        {/* Playhead Scrubber */}
        <div
          style={{ left: `${playheadPercent}%` }}
          className="absolute top-0 bottom-0 w-0.5 bg-blue-400 z-30 pointer-events-none shadow-[0_0_6px_#60a5fa]"
        >
          <div className="w-2.5 h-2.5 -ml-1 bg-blue-400 rounded-full shadow border border-white" />
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-400 pt-1">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-rose-500 border border-rose-400" />
          <span>Critical</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-orange-500 border border-orange-400" />
          <span>High</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-amber-500 border border-amber-400" />
          <span>Medium</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm bg-blue-500 border border-blue-400" />
          <span>Low</span>
        </div>
        <span className="text-slate-600">|</span>
        <span className="text-slate-500 italic">Click event marker to seek video and inspect</span>
      </div>
    </div>
  );
}
