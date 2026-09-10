"use client";

/**
 * BoxOverlay — renders YOLO bounding boxes as an SVG overlay on top of a <video> element.
 *
 * Usage:
 *   <div style={{ position: "relative" }}>
 *     <video ref={videoRef} ... />
 *     <BoxOverlay trackFrames={trackFrames} videoRef={videoRef} />
 *   </div>
 *
 * Props:
 *   trackFrames  – array of TrackFrame objects from tracks.jsonl.gz
 *   videoRef     – ref to the <video> element (for sizing and currentTime)
 */

import React, { useEffect, useRef, useState } from "react";

export interface TrackObservation {
  track_id: number;
  class_id: string;
  confidence: number;
  bbox_xyxy_norm: [number, number, number, number];
  is_interpolated: boolean;
}

export interface TrackFrame {
  schema_version: string;
  frame_index: number;
  timestamp_ms: number;
  frame_width: number;
  frame_height: number;
  tracks: TrackObservation[];
}

interface BoxOverlayProps {
  trackFrames: TrackFrame[];
  videoRef: React.RefObject<HTMLVideoElement | null>;
}

const CLASS_COLORS: Record<string, string> = {
  person: "#22d3ee",     // cyan
  package: "#f59e0b",    // amber
  pallet: "#86efac",     // green
  equipment: "#c084fc",  // purple
};

function getClassColor(classId: string): string {
  return CLASS_COLORS[classId] ?? "#94a3b8"; // slate fallback
}

/**
 * Find the nearest track frame to the given video time (ms).
 * Returns null if trackFrames is empty or the nearest frame is > 200 ms away.
 */
function findNearestFrame(
  trackFrames: TrackFrame[],
  currentMs: number
): TrackFrame | null {
  if (trackFrames.length === 0) return null;

  let best: TrackFrame | null = null;
  let bestDelta = Infinity;

  for (const tf of trackFrames) {
    const delta = Math.abs(tf.timestamp_ms - currentMs);
    if (delta < bestDelta) {
      bestDelta = delta;
      best = tf;
    }
    // Early exit: frames are sorted by time, so once delta grows we're past the minimum
    if (tf.timestamp_ms > currentMs + 500) break;
  }

  // Don't draw stale boxes if the nearest frame is very far away
  return bestDelta <= 500 ? best : null;
}

export function BoxOverlay({ trackFrames, videoRef }: BoxOverlayProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [currentTracks, setCurrentTracks] = useState<TrackObservation[]>([]);
  const [svgSize, setSvgSize] = useState({ w: 0, h: 0 });

  // Sync SVG size to video element
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const updateSize = () => {
      setSvgSize({ w: video.clientWidth, h: video.clientHeight });
    };
    updateSize();

    const ro = new ResizeObserver(updateSize);
    ro.observe(video);
    return () => ro.disconnect();
  }, [videoRef]);

  // Update bounding boxes on each timeupdate event
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const onTimeUpdate = () => {
      const currentMs = video.currentTime * 1000;
      const frame = findNearestFrame(trackFrames, currentMs);
      setCurrentTracks(frame ? frame.tracks : []);
    };

    video.addEventListener("timeupdate", onTimeUpdate);
    return () => video.removeEventListener("timeupdate", onTimeUpdate);
  }, [videoRef, trackFrames]);

  if (svgSize.w === 0 || svgSize.h === 0) return null;

  return (
    <svg
      ref={svgRef}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: svgSize.w,
        height: svgSize.h,
        pointerEvents: "none",
        zIndex: 10,
      }}
      viewBox={`0 0 ${svgSize.w} ${svgSize.h}`}
      aria-label="AI detection overlay"
    >
      {currentTracks.map((track) => {
        const [x1n, y1n, x2n, y2n] = track.bbox_xyxy_norm;
        const x = x1n * svgSize.w;
        const y = y1n * svgSize.h;
        const bw = (x2n - x1n) * svgSize.w;
        const bh = (y2n - y1n) * svgSize.h;
        const color = getClassColor(track.class_id);
        const labelY = y > 16 ? y - 4 : y + bh + 14;

        return (
          <g key={`${track.track_id}-${track.class_id}`}>
            {/* Bounding box rectangle */}
            <rect
              x={x}
              y={y}
              width={bw}
              height={bh}
              fill="none"
              stroke={color}
              strokeWidth={track.is_interpolated ? 1 : 2}
              strokeDasharray={track.is_interpolated ? "4 3" : undefined}
              opacity={0.9}
            />
            {/* Label background pill */}
            <rect
              x={x}
              y={labelY - 11}
              width={Math.max(60, track.class_id.length * 7 + 30)}
              height={14}
              rx={3}
              fill={color}
              opacity={0.85}
            />
            {/* Label text */}
            <text
              x={x + 4}
              y={labelY}
              fill="#0f172a"
              fontSize={10}
              fontFamily="ui-monospace, SFMono-Regular, monospace"
              fontWeight="bold"
            >
              {track.class_id} #{track.track_id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
