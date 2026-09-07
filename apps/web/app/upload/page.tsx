"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  UploadCloud,
  FileVideo,
  CheckCircle2,
  AlertCircle,
  Clock,
  HardDrive,
  Maximize2,
  Film,
  Camera,
  Loader2,
  ArrowRight,
} from "lucide-react";
import { api, ApiError, ProblemDetails } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { components } from "@/lib/schema";

type CameraProfile = components["schemas"]["CameraProfileResponse"];

export default function UploadPage() {
  const router = useRouter();

  // Form states
  const [file, setFile] = useState<File | null>(null);
  const [cameraProfiles, setCameraProfiles] = useState<CameraProfile[]>([]);
  const [selectedProfileKey, setSelectedProfileKey] = useState<string>("");
  const [mode, setMode] = useState<"LIVE" | "REPLAY">("LIVE");
  const [sourceConsent, setSourceConsent] = useState(false);

  // Status & error states
  const [loadingProfiles, setLoadingProfiles] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progressStage, setProgressStage] = useState<string>("");
  const [dragOver, setDragOver] = useState(false);
  const [errorProblem, setErrorProblem] = useState<ProblemDetails | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);

  // Load camera profiles on mount
  useEffect(() => {
    async function loadProfiles() {
      try {
        setLoadingProfiles(true);
        const profiles = await api.getCameraProfiles();
        setCameraProfiles(profiles);
        if (profiles.length > 0) {
          // Default to first profile (e.g. demo-camera)
          setSelectedProfileKey(`${profiles[0].id}:${profiles[0].version}`);
        }
      } catch (err: unknown) {
        if (err instanceof ApiError) {
          setErrorProblem(err.problem);
        } else {
          setGeneralError("Failed to fetch camera profiles from server.");
        }
      } finally {
        setLoadingProfiles(false);
      }
    }
    loadProfiles();
  }, []);

  const handleFileSelect = (selected: File) => {
    setErrorProblem(null);
    setGeneralError(null);

    if (!selected.name.toLowerCase().endsWith(".mp4") && selected.type !== "video/mp4") {
      setGeneralError("Invalid file type. Only MP4 videos are supported.");
      return;
    }

    const maxSize = 500 * 1024 * 1024; // 500 MB
    if (selected.size > maxSize) {
      setGeneralError("File exceeds maximum allowed size of 500 MB.");
      return;
    }

    setFile(selected);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !sourceConsent || !selectedProfileKey) return;

    const [profileId, profileVersionStr] = selectedProfileKey.split(":");
    const profileVersion = parseInt(profileVersionStr, 10);

    setUploading(true);
    setErrorProblem(null);
    setGeneralError(null);

    try {
      // Step 1: Upload Video
      setProgressStage("Uploading MP4 video container...");
      const video = await api.uploadVideo(file);

      // Step 2: Create Analysis Run
      setProgressStage("Ingestion validated. Scheduling analysis run...");
      const runAccepted = await api.createRun({
        video_id: video.id,
        camera_profile_id: profileId,
        camera_profile_version: profileVersion,
        mode,
      });

      // Step 3: Redirect to Run Detail view
      setProgressStage("Run enqueued! Redirecting to run monitor...");
      router.push(`/runs/${runAccepted.run_id}`);
    } catch (err: unknown) {
      setUploading(false);
      setProgressStage("");
      if (err instanceof ApiError) {
        setErrorProblem(err.problem);
      } else {
        setGeneralError((err as Error).message || "An unexpected error occurred during upload.");
      }
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-3">
          <UploadCloud className="w-7 h-7 text-blue-500" />
          Upload Warehouse Video
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Submit surveillance footage for automated risk behavior detection, tracking, and evidence generation.
        </p>
      </div>

      {/* Constraints Card */}
      <Card className="bg-slate-900/60 border-slate-800">
        <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
          <Film className="w-4 h-4 text-blue-400" />
          Ingest Validation Constraints (Blueprint §8.2)
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <div className="flex items-center gap-2 text-slate-300">
            <Film className="w-4 h-4 text-slate-500 shrink-0" />
            <div>
              <div className="font-medium text-slate-200">Format</div>
              <div className="text-slate-400">MP4 (H.264)</div>
            </div>
          </div>
          <div className="flex items-center gap-2 text-slate-300">
            <HardDrive className="w-4 h-4 text-slate-500 shrink-0" />
            <div>
              <div className="font-medium text-slate-200">Max Size</div>
              <div className="text-slate-400">500 MB</div>
            </div>
          </div>
          <div className="flex items-center gap-2 text-slate-300">
            <Clock className="w-4 h-4 text-slate-500 shrink-0" />
            <div>
              <div className="font-medium text-slate-200">Max Duration</div>
              <div className="text-slate-400">600s (10 min)</div>
            </div>
          </div>
          <div className="flex items-center gap-2 text-slate-300">
            <Maximize2 className="w-4 h-4 text-slate-500 shrink-0" />
            <div>
              <div className="font-medium text-slate-200">Max Resolution</div>
              <div className="text-slate-400">4K (3840×2160)</div>
            </div>
          </div>
        </div>
      </Card>

      {/* Error Banners */}
      {errorProblem && (
        <Alert variant="danger" title={`${errorProblem.title} (${errorProblem.code})`}>
          <div className="space-y-1">
            <p>{errorProblem.detail}</p>
            {errorProblem.errors && errorProblem.errors.length > 0 && (
              <ul className="list-disc list-inside mt-2 space-y-0.5 text-rose-300">
                {errorProblem.errors.map((e, idx) => (
                  <li key={idx}>
                    <span className="font-mono">{e.field}</span>: {e.reason}
                  </li>
                ))}
              </ul>
            )}
            <div className="text-[10px] text-rose-400 font-mono mt-2">
              Request ID: {errorProblem.request_id}
            </div>
          </div>
        </Alert>
      )}

      {generalError && (
        <Alert variant="danger" title="Validation Failed">
          {generalError}
        </Alert>
      )}

      {/* Upload Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Drag and Drop Zone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
            dragOver
              ? "border-blue-500 bg-blue-950/20"
              : file
              ? "border-emerald-500/50 bg-emerald-950/10"
              : "border-slate-800 bg-slate-900/30 hover:border-slate-700"
          }`}
        >
          {file ? (
            <div className="flex flex-col items-center gap-3">
              <CheckCircle2 className="w-12 h-12 text-emerald-400" />
              <div>
                <div className="font-medium text-slate-100">{file.name}</div>
                <div className="text-xs text-slate-400 mt-0.5">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setFile(null)}
                disabled={uploading}
              >
                Change File
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <FileVideo className="w-12 h-12 text-slate-500" />
              <div>
                <span className="text-sm font-medium text-slate-200">
                  Drag and drop your MP4 footage here, or{" "}
                </span>
                <label className="text-sm font-medium text-blue-400 hover:text-blue-300 cursor-pointer underline">
                  browse files
                  <input
                    type="file"
                    accept="video/mp4,.mp4"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleFileSelect(e.target.files[0]);
                      }
                    }}
                    disabled={uploading}
                  />
                </label>
              </div>
              <p className="text-xs text-slate-500">Supports standard H.264 MP4 videos up to 500 MB</p>
            </div>
          )}
        </div>

        {/* Configuration Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Camera Profile Selector */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-200">
              Camera Profile & Calibration
            </label>
            {loadingProfiles ? (
              <div className="flex items-center gap-2 text-xs text-slate-500 py-2">
                <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                Loading calibrated profiles...
              </div>
            ) : cameraProfiles.length === 0 ? (
              <div className="text-xs text-amber-400 bg-amber-950/20 border border-amber-900/50 p-3 rounded-lg flex items-center justify-between">
                <span>No camera profiles found. Please calibrate one first.</span>
                <Link href="/settings/camera" className="text-blue-400 underline font-medium">
                  Create Profile
                </Link>
              </div>
            ) : (
              <div className="space-y-1">
                <select
                  value={selectedProfileKey}
                  onChange={(e) => setSelectedProfileKey(e.target.value)}
                  disabled={uploading}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  {cameraProfiles.map((p) => (
                    <option key={`${p.id}:${p.version}`} value={`${p.id}:${p.version}`}>
                      {p.name} ({p.id} v{p.version}) - {p.zones?.length || 0} zones
                    </option>
                  ))}
                </select>
                <div className="flex items-center justify-between text-[11px] text-slate-500 px-1">
                  <span>Zones & floor defined in camera setup</span>
                  <Link
                    href="/settings/camera"
                    className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                  >
                    <Camera className="w-3 h-3" />
                    Calibrate New
                  </Link>
                </div>
              </div>
            )}
          </div>

          {/* Analysis Mode */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-200">Analysis Mode</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setMode("LIVE")}
                disabled={uploading}
                className={`px-4 py-2.5 rounded-lg border text-sm font-medium text-left transition-colors cursor-pointer ${
                  mode === "LIVE"
                    ? "bg-blue-950/50 border-blue-500 text-blue-300"
                    : "bg-slate-900/40 border-slate-800 text-slate-400 hover:border-slate-700"
                }`}
              >
                <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                  <Badge variant="success">LIVE</Badge>
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Full multi-engine pipeline inference
                </div>
              </button>

              <button
                type="button"
                onClick={() => setMode("REPLAY")}
                disabled={uploading}
                className={`px-4 py-2.5 rounded-lg border text-sm font-medium text-left transition-colors cursor-pointer ${
                  mode === "REPLAY"
                    ? "bg-amber-950/50 border-amber-500 text-amber-300"
                    : "bg-slate-900/40 border-slate-800 text-slate-400 hover:border-slate-700"
                }`}
              >
                <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                  <Badge variant="warning">REPLAY</Badge>
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Deterministic observation replay
                </div>
              </button>
            </div>
            {mode === "REPLAY" && (
              <p className="text-[11px] text-amber-400/90 italic">
                Replay mode — detections loaded from a previously generated artifact.
              </p>
            )}
          </div>
        </div>

        {/* Source Consent Mandatory Checkbox (Blueprint §8.4 & §16.1) */}
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50 space-y-2">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={sourceConsent}
              onChange={(e) => setSourceConsent(e.target.checked)}
              disabled={uploading}
              className="mt-1 h-4 w-4 rounded border-slate-700 bg-slate-800 text-blue-600 focus:ring-blue-500"
            />
            <div className="text-xs text-slate-300 leading-relaxed">
              <span className="font-semibold text-slate-200">Mandatory Source Consent: </span>
              I confirm that this video footage was captured with appropriate notice and authorization for
              internal warehouse quality assurance and risk evaluation, in accordance with Section 8.4 data
              handling policy.
            </div>
          </label>
        </div>

        {/* Upload Button & Progress */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-800">
          <div className="text-xs text-slate-500">
            {uploading ? (
              <span className="flex items-center gap-2 text-blue-400 font-medium">
                <Loader2 className="w-4 h-4 animate-spin" />
                {progressStage}
              </span>
            ) : (
              "All processing runs are logged and reproducible via run manifests."
            )}
          </div>

          <Button
            type="submit"
            size="lg"
            variant="primary"
            disabled={!file || !sourceConsent || !selectedProfileKey || uploading}
            className="w-full sm:w-auto flex items-center justify-center gap-2"
          >
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Ingesting...
              </>
            ) : (
              <>
                Upload & Analyze Video
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
