"use client";

import React, { useEffect, useState } from "react";
import {
  Camera,
  Layers,
  Save,
  CheckCircle2,
  AlertTriangle,
  Info,
  RotateCcw,
  Plus,
  Copy,
} from "lucide-react";
import { api, ApiError, ProblemDetails } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import {
  PolygonEditor,
  Point,
  PolygonZone,
  SupportRegion,
} from "@/components/camera/PolygonEditor";
import type { components } from "@/lib/schema";

type CameraProfile = components["schemas"]["CameraProfileResponse"];

// Shoelace formula for polygon area
function calculatePolygonArea(points: Point[]): number {
  if (points.length < 3) return 0;
  let area = 0;
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    area += points[i][0] * points[j][1];
    area -= points[j][0] * points[i][1];
  }
  return Math.abs(area) / 2;
}

// Convex check for 2D polygon using cross-product sign consistency
function isPolygonConvex(points: Point[]): boolean {
  if (points.length < 3) return false;
  const n = points.length;
  let prevSign = 0;

  for (let i = 0; i < n; i++) {
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const p3 = points[(i + 2) % n];

    const dx1 = p2[0] - p1[0];
    const dy1 = p2[1] - p1[1];
    const dx2 = p3[0] - p2[0];
    const dy2 = p3[1] - p2[1];

    const cross = dx1 * dy2 - dy1 * dx2;
    // Disregard collinear points within floating precision
    if (Math.abs(cross) > 1e-6) {
      const sign = cross > 0 ? 1 : -1;
      if (prevSign === 0) {
        prevSign = sign;
      } else if (sign !== prevSign) {
        return false;
      }
    }
  }
  return true;
}

const DEFAULT_FLOOR: Point[] = [
  [0.02, 0.55],
  [0.98, 0.55],
  [0.98, 0.98],
  [0.02, 0.98],
];

const DEFAULT_ZONES: PolygonZone[] = [
  {
    id: "loading",
    kind: "ALLOWED",
    severity: "NORMAL",
    polygon: [
      [0.05, 0.6],
      [0.6, 0.6],
      [0.6, 0.95],
      [0.05, 0.95],
    ],
  },
  {
    id: "edge",
    kind: "PROHIBITED",
    severity: "CRITICAL",
    polygon: [
      [0.75, 0.55],
      [0.98, 0.55],
      [0.98, 0.98],
      [0.75, 0.98],
    ],
  },
];

const DEFAULT_SUPPORT: SupportRegion[] = [
  {
    id: "pallet-a-visible-top",
    label: "Visible pallet A top",
    polygon: [
      [0.18, 0.62],
      [0.53, 0.6],
      [0.58, 0.83],
      [0.16, 0.85],
    ],
  },
];

export default function CameraCalibrationPage() {
  const [profiles, setProfiles] = useState<CameraProfile[]>([]);
  const [loadingList, setLoadingList] = useState(true);

  // Form State
  const [profileId, setProfileId] = useState("demo-camera");
  const [profileName, setProfileName] = useState("Demo fixed camera");
  const [aspectRatio, setAspectRatio] = useState(1.777778); // 16:9
  const [floorPolygon, setFloorPolygon] = useState<Point[]>(DEFAULT_FLOOR);
  const [zones, setZones] = useState<PolygonZone[]>(DEFAULT_ZONES);
  const [supportRegions, setSupportRegions] = useState<SupportRegion[]>(DEFAULT_SUPPORT);
  const [supportConfirmed, setSupportConfirmed] = useState(false);

  // UI state
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [errorProblem, setErrorProblem] = useState<ProblemDetails | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const fetchProfiles = async () => {
    try {
      setLoadingList(true);
      const data = await api.getCameraProfiles();
      setProfiles(data);
    } catch {
      // Ignore initial load failure
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, []);

  const loadProfileIntoEditor = (p: CameraProfile) => {
    setProfileId(p.id);
    setProfileName(p.name);
    setAspectRatio(p.frame_aspect_ratio);
    setFloorPolygon(p.floor_polygon as Point[]);
    setZones(p.zones as PolygonZone[]);
    setSupportRegions(p.support_regions as SupportRegion[]);
    setSupportConfirmed(p.support_regions.length === 0);
    setSaveSuccess(null);
    setErrorProblem(null);
    setValidationError(null);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveSuccess(null);
    setErrorProblem(null);
    setValidationError(null);

    // Client-side validations per Blueprint Section 12.1
    if (!/^[a-z0-9][a-z0-9-]{1,63}$/.test(profileId)) {
      setValidationError(
        "Profile ID must match regex ^[a-z0-9][a-z0-9-]{1,63}$ (lowercase, digits, hyphens)."
      );
      return;
    }

    if (profileName.trim().length < 1 || profileName.length > 100) {
      setValidationError("Profile Name must be between 1 and 100 characters.");
      return;
    }

    if (floorPolygon.length < 3 || floorPolygon.length > 32) {
      setValidationError("Floor polygon must have between 3 and 32 vertices.");
      return;
    }

    const floorArea = calculatePolygonArea(floorPolygon);
    if (floorArea < 0.005) {
      setValidationError("Floor polygon area must be at least 0.5% (0.005) of the frame.");
      return;
    }

    // Validate Zones
    for (const z of zones) {
      if (z.polygon.length < 3 || z.polygon.length > 32) {
        setValidationError(`Zone '${z.id}' must have between 3 and 32 vertices.`);
        return;
      }
      if (calculatePolygonArea(z.polygon) < 0.005) {
        setValidationError(`Zone '${z.id}' area must be at least 0.5% of the frame.`);
        return;
      }
    }

    // Validate Support Regions
    for (const s of supportRegions) {
      if (s.polygon.length < 3 || s.polygon.length > 32) {
        setValidationError(`Support region '${s.label}' must have between 3 and 32 vertices.`);
        return;
      }
      if (!isPolygonConvex(s.polygon)) {
        setValidationError(
          `Support region '${s.label}' MUST be convex according to Blueprint Section 12.1.`
        );
        return;
      }
    }

    if (supportRegions.length > 0 && !supportConfirmed) {
      setValidationError(
        "Operator confirmation required: You must explicitly confirm that every support polygon marks a visible load-bearing top surface."
      );
      return;
    }

    setSaving(true);
    try {
      const created = await api.createCameraProfile({
        id: profileId,
        name: profileName,
        frame_aspect_ratio: aspectRatio,
        floor_polygon: floorPolygon,
        zones,
        support_regions: supportRegions,
      });

      setSaveSuccess(
        `Profile '${created.id}' v${created.version} saved successfully (SHA-256: ${created.sha256.slice(
          0,
          8
        )}...).`
      );
      fetchProfiles();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorProblem(err.problem);
      } else {
        setValidationError((err as Error).message || "Failed to save camera profile.");
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-3">
          <Camera className="w-7 h-7 text-blue-500" />
          Camera Calibration & Spatial Setup
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Configure immutable camera profiles defining floor boundaries, prohibited zones, and visible support surfaces (Blueprint §12.1).
        </p>
      </div>

      {saveSuccess && (
        <Alert variant="success" title="Profile Saved">
          {saveSuccess}
        </Alert>
      )}

      {errorProblem && (
        <Alert variant="danger" title={`${errorProblem.title} (${errorProblem.code})`}>
          <div className="space-y-1">
            <p>{errorProblem.detail}</p>
            {errorProblem.errors?.map((e, idx) => (
              <div key={idx} className="text-xs text-rose-300 font-mono">
                {e.field}: {e.reason}
              </div>
            ))}
          </div>
        </Alert>
      )}

      {validationError && (
        <Alert variant="danger" title="Calibration Rule Violation">
          {validationError}
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left 2 Cols: Interactive Polygon Canvas */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
              <div>
                <h3 className="text-base font-semibold text-slate-100">
                  Interactive Spatial Canvas
                </h3>
                <p className="text-xs text-slate-400">
                  Click on canvas to add vertex; drag to reposition; use trash icon to remove.
                </p>
              </div>
              <Badge variant="neutral">Aspect {aspectRatio.toFixed(3)}</Badge>
            </div>

            <PolygonEditor
              aspectRatio={aspectRatio}
              floorPolygon={floorPolygon}
              onFloorPolygonChange={setFloorPolygon}
              zones={zones}
              onZonesChange={setZones}
              supportRegions={supportRegions}
              onSupportRegionsChange={setSupportRegions}
            />
          </Card>

          {/* Section 12.1 Operator Notice */}
          <div className="p-4 rounded-xl border border-amber-900/50 bg-amber-950/20 space-y-3">
            <div className="flex items-start gap-2 text-amber-300 font-semibold text-xs">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              Blueprint §12.1 Spatial Integrity Rules
            </div>
            <p className="text-xs text-amber-200/90 leading-relaxed">
              Every polygon must contain 3–32 unique, non-self-intersecting points with area &ge; 0.5% of the frame.
              Support polygons <span className="font-semibold text-white">MUST be convex</span>. If no visible load-bearing top surface exists, support regions must be left empty so that overhang rules are safely disabled rather than falsely triggered.
            </p>
            {supportRegions.length > 0 && (
              <label className="flex items-start gap-2 pt-2 border-t border-amber-900/40 cursor-pointer">
                <input
                  type="checkbox"
                  checked={supportConfirmed}
                  onChange={(e) => setSupportConfirmed(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-amber-700 bg-slate-900 text-amber-500 focus:ring-amber-400"
                />
                <span className="text-xs text-amber-100 font-medium">
                  Operator Confirmation: I explicitly confirm that every defined support polygon marks a visible load-bearing top surface.
                </span>
              </label>
            )}
          </div>
        </div>

        {/* Right Col: Metadata & Version History */}
        <div className="space-y-6">
          {/* Metadata Form */}
          <Card>
            <h3 className="text-base font-semibold text-slate-100 mb-4">Profile Metadata</h3>
            <form onSubmit={handleSave} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Camera Profile ID
                </label>
                <input
                  type="text"
                  value={profileId}
                  onChange={(e) => setProfileId(e.target.value.toLowerCase())}
                  placeholder="e.g. demo-camera"
                  required
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
                />
                <span className="text-[10px] text-slate-500">
                  Lowercase alphanumeric + hyphens (^[a-z0-9][a-z0-9-]{"{1,63}"}$)
                </span>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Camera Name
                </label>
                <input
                  type="text"
                  value={profileName}
                  onChange={(e) => setProfileName(e.target.value)}
                  placeholder="e.g. Demo fixed camera"
                  required
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Aspect Ratio
                </label>
                <input
                  type="number"
                  step="0.000001"
                  value={aspectRatio}
                  onChange={(e) => setAspectRatio(parseFloat(e.target.value) || 1.777778)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
                />
                <span className="text-[10px] text-slate-500">1.777778 for standard 16:9 frame</span>
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  disabled={saving}
                  className="w-full flex items-center justify-center gap-2"
                >
                  <Save className="w-4 h-4" />
                  {saving ? "Saving Immutable Version..." : "Save Profile Version"}
                </Button>
              </div>
            </form>
          </Card>

          {/* Calibrated Profiles Registry */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                <Layers className="w-4 h-4 text-slate-400" />
                Active Profiles ({profiles.length})
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchProfiles}
                className="text-xs p-1 h-auto text-slate-400"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </Button>
            </div>

            {loadingList ? (
              <div className="py-6 text-center text-xs text-slate-500">Loading registry...</div>
            ) : profiles.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-500">
                No profiles saved in database yet.
              </div>
            ) : (
              <div className="space-y-3">
                {profiles.map((p) => (
                  <div
                    key={`${p.id}:${p.version}`}
                    className="p-3 rounded-lg border border-slate-800 bg-slate-900/50 hover:border-slate-700 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-xs font-semibold text-slate-200">{p.name}</div>
                        <div className="text-[11px] font-mono text-slate-400">
                          {p.id} <Badge variant="low">v{p.version}</Badge>
                        </div>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => loadProfileIntoEditor(p)}
                        className="text-[11px] py-1 px-2 h-auto flex items-center gap-1"
                      >
                        <Copy className="w-3 h-3" />
                        Load
                      </Button>
                    </div>
                    <div className="mt-2 text-[10px] text-slate-500 flex items-center justify-between">
                      <span>
                        {p.zones?.length || 0} zones · {p.support_regions?.length || 0} support
                      </span>
                      <span className="font-mono text-slate-600">{p.sha256.slice(0, 8)}...</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
