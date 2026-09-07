"use client";

import React, { useRef, useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

export type Point = [number, number];

export interface PolygonZone {
  id: string;
  kind: "ALLOWED" | "PROHIBITED";
  severity: "NORMAL" | "CRITICAL";
  polygon: Point[];
}

export interface SupportRegion {
  id: string;
  label: string;
  polygon: Point[];
}

interface PolygonEditorProps {
  aspectRatio: number;
  floorPolygon: Point[];
  onFloorPolygonChange: (poly: Point[]) => void;
  zones: PolygonZone[];
  onZonesChange: (zones: PolygonZone[]) => void;
  supportRegions: SupportRegion[];
  onSupportRegionsChange: (regions: SupportRegion[]) => void;
}

export function PolygonEditor({
  aspectRatio,
  floorPolygon,
  onFloorPolygonChange,
  zones,
  onZonesChange,
  supportRegions,
  onSupportRegionsChange,
}: PolygonEditorProps) {
  const [activeLayer, setActiveLayer] = useState<"floor" | "zone" | "support">("floor");
  const [selectedZoneIndex, setSelectedZoneIndex] = useState<number>(0);
  const [selectedSupportIndex, setSelectedSupportIndex] = useState<number>(0);
  const [draggedPoint, setDraggedPoint] = useState<{ index: number } | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);

  // Get currently editable polygon points
  const getCurrentPoints = (): Point[] => {
    if (activeLayer === "floor") return floorPolygon;
    if (activeLayer === "zone") return zones[selectedZoneIndex]?.polygon || [];
    if (activeLayer === "support") return supportRegions[selectedSupportIndex]?.polygon || [];
    return [];
  };

  const updateCurrentPoints = (newPoints: Point[]) => {
    if (activeLayer === "floor") {
      onFloorPolygonChange(newPoints);
    } else if (activeLayer === "zone" && zones[selectedZoneIndex]) {
      const updated = [...zones];
      updated[selectedZoneIndex] = { ...updated[selectedZoneIndex], polygon: newPoints };
      onZonesChange(updated);
    } else if (activeLayer === "support" && supportRegions[selectedSupportIndex]) {
      const updated = [...supportRegions];
      updated[selectedSupportIndex] = { ...updated[selectedSupportIndex], polygon: newPoints };
      onSupportRegionsChange(updated);
    }
  };

  const handleSvgClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (draggedPoint) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

    const current = getCurrentPoints();
    if (current.length >= 32) return; // Max 32 points per Section 12.1

    updateCurrentPoints([...current, [Number(x.toFixed(4)), Number(y.toFixed(4))]]);
  };

  const handlePointMouseDown = (index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setDraggedPoint({ index });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!draggedPoint || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

    const current = [...getCurrentPoints()];
    current[draggedPoint.index] = [Number(x.toFixed(4)), Number(y.toFixed(4))];
    updateCurrentPoints(current);
  };

  const handleMouseUp = () => {
    setDraggedPoint(null);
  };

  const removePoint = (index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const current = getCurrentPoints();
    if (current.length <= 3) return; // Must have at least 3 points
    updateCurrentPoints(current.filter((_, i) => i !== index));
  };

  const clearCurrent = () => {
    updateCurrentPoints([]);
  };

  return (
    <div className="space-y-4">
      {/* Layer selector tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 pb-3">
        <Button
          variant={activeLayer === "floor" ? "primary" : "ghost"}
          size="sm"
          onClick={() => setActiveLayer("floor")}
        >
          Floor Polygon ({floorPolygon.length} pts)
        </Button>
        <Button
          variant={activeLayer === "zone" ? "primary" : "ghost"}
          size="sm"
          onClick={() => setActiveLayer("zone")}
        >
          Zones ({zones.length})
        </Button>
        <Button
          variant={activeLayer === "support" ? "primary" : "ghost"}
          size="sm"
          onClick={() => setActiveLayer("support")}
        >
          Visible Support Regions ({supportRegions.length})
        </Button>
      </div>

      {/* Sub-controls for Zone or Support layers */}
      {activeLayer === "zone" && (
        <div className="flex items-center gap-2 flex-wrap">
          {zones.map((z, idx) => (
            <button
              key={z.id}
              onClick={() => setSelectedZoneIndex(idx)}
              className={`px-3 py-1 rounded text-xs font-mono border cursor-pointer ${
                selectedZoneIndex === idx
                  ? "bg-blue-950 border-blue-500 text-blue-300"
                  : "bg-slate-900 border-slate-800 text-slate-400"
              }`}
            >
              {z.id} ({z.kind})
            </button>
          ))}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              const newZone: PolygonZone = {
                id: `zone-${zones.length + 1}`,
                kind: "PROHIBITED",
                severity: "CRITICAL",
                polygon: [
                  [0.75, 0.55],
                  [0.98, 0.55],
                  [0.98, 0.98],
                  [0.75, 0.98],
                ],
              };
              onZonesChange([...zones, newZone]);
              setSelectedZoneIndex(zones.length);
            }}
          >
            + Add Zone
          </Button>
        </div>
      )}

      {activeLayer === "support" && (
        <div className="flex items-center gap-2 flex-wrap">
          {supportRegions.map((s, idx) => (
            <button
              key={s.id}
              onClick={() => setSelectedSupportIndex(idx)}
              className={`px-3 py-1 rounded text-xs font-mono border cursor-pointer ${
                selectedSupportIndex === idx
                  ? "bg-amber-950 border-amber-500 text-amber-300"
                  : "bg-slate-900 border-slate-800 text-slate-400"
              }`}
            >
              {s.label} ({s.polygon.length} pts)
            </button>
          ))}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              const newSupport: SupportRegion = {
                id: `pallet-${supportRegions.length + 1}`,
                label: `Pallet Top ${supportRegions.length + 1}`,
                polygon: [
                  [0.2, 0.6],
                  [0.5, 0.6],
                  [0.55, 0.85],
                  [0.18, 0.85],
                ],
              };
              onSupportRegionsChange([...supportRegions, newSupport]);
              setSelectedSupportIndex(supportRegions.length);
            }}
          >
            + Add Visible Support
          </Button>
        </div>
      )}

      {/* Interactive SVG Canvas */}
      <div
        ref={containerRef}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        className="relative bg-slate-950 border border-slate-800 rounded-xl overflow-hidden select-none"
        style={{ aspectRatio: `${aspectRatio}` }}
      >
        {/* Background grid representing video frame canvas */}
        <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:24px_24px] opacity-40 pointer-events-none" />

        <svg
          className="absolute inset-0 w-full h-full cursor-crosshair"
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          onClick={handleSvgClick}
        >
          {/* Render Floor Polygon (Cyan) */}
          {floorPolygon.length >= 3 && (
            <polygon
              points={floorPolygon.map(([x, y]) => `${x},${y}`).join(" ")}
              fill="rgba(6, 182, 212, 0.15)"
              stroke="#06b6d4"
              strokeWidth="0.003"
              strokeDasharray={activeLayer === "floor" ? "none" : "0.01 0.01"}
            />
          )}

          {/* Render Zones */}
          {zones.map((z, idx) => {
            if (z.polygon.length < 3) return null;
            const isAllowed = z.kind === "ALLOWED";
            const isSelected = activeLayer === "zone" && selectedZoneIndex === idx;
            return (
              <polygon
                key={z.id}
                points={z.polygon.map(([x, y]) => `${x},${y}`).join(" ")}
                fill={isAllowed ? "rgba(16, 185, 129, 0.2)" : "rgba(244, 63, 94, 0.2)"}
                stroke={isAllowed ? "#10b981" : "#f43f5e"}
                strokeWidth={isSelected ? "0.005" : "0.003"}
              />
            );
          })}

          {/* Render Support Regions (Amber) */}
          {supportRegions.map((s, idx) => {
            if (s.polygon.length < 3) return null;
            const isSelected = activeLayer === "support" && selectedSupportIndex === idx;
            return (
              <polygon
                key={s.id}
                points={s.polygon.map(([x, y]) => `${x},${y}`).join(" ")}
                fill="rgba(245, 158, 11, 0.2)"
                stroke="#f59e0b"
                strokeWidth={isSelected ? "0.005" : "0.003"}
              />
            );
          })}

          {/* Active Polygon Draggable Vertices */}
          {getCurrentPoints().map(([x, y], idx) => (
            <g key={idx}>
              <circle
                cx={x}
                cy={y}
                r="0.012"
                fill="#38bdf8"
                stroke="#ffffff"
                strokeWidth="0.003"
                className="cursor-move hover:scale-125 transition-transform"
                onMouseDown={(e) => handlePointMouseDown(idx, e)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  removePoint(idx, e);
                }}
              />
            </g>
          ))}
        </svg>

        {/* Top-right helper text */}
        <div className="absolute top-3 right-3 bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded-md text-[11px] font-mono text-slate-400 pointer-events-none">
          Click canvas to add point &bull; Drag point to move &bull; Right-click point to delete
        </div>

        {/* Bottom controls */}
        <div className="absolute bottom-3 right-3 flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={clearCurrent}>
            <Trash2 className="w-3.5 h-3.5 mr-1" />
            Reset Layer
          </Button>
        </div>
      </div>
    </div>
  );
}
