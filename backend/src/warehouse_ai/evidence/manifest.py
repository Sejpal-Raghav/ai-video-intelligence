"""Run reproducibility manifest generator matching Blueprint Section 13."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_git_info() -> dict[str, Any]:
    """Retrieve git commit hash and dirty status."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        dirty = len(status) > 0
        return {"git_commit": commit, "dirty": dirty}
    except Exception:
        return {"git_commit": "0" * 40, "dirty": False}


def build_run_manifest(
    run_id: str,
    video_id: str,
    video_sha256: str,
    video_duration_ms: int,
    normalized_media_sha256: str,
    model_backend: str,
    model_sha256: str,
    rules_version: str,
    rules_sha256: str,
    risk_policy_version: str,
    risk_policy_sha256: str,
    camera_profile_id: str,
    camera_profile_sha256: str,
    mode: str,
    inference_fps: int,
    verify_fps: int,
    started_at: str,
    finished_at: str,
    artifacts: list[dict[str, Any]],
    event_ids: list[str],
    device: str = "cpu",
    dependency_lock_sha256: str = "0" * 64,
) -> dict[str, Any]:
    """Construct schema-compliant run-manifest.v1 object."""
    git_info = get_git_info()

    # The artifact list strictly excludes the manifest itself
    filtered_artifacts = [a for a in artifacts if a.get("kind") != "MANIFEST"]

    manifest = {
        "schema_version": "run-manifest.v1",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "video_id": video_id,
            "sha256": video_sha256,
            "duration_ms": video_duration_ms,
        },
        "normalized_media_sha256": normalized_media_sha256,
        "code": git_info,
        "runtime": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "os": f"{platform.system()} {platform.release()}",
            "device": device,
            "precision": "fp32",
            "random_seed": 42,
            "dependency_lock_sha256": dependency_lock_sha256,
        },
        "model": {
            "backend": model_backend,
            "name": "warehouse-v1",
            "sha256": model_sha256,
        },
        "config": {
            "behavior_rules_version": rules_version,
            "behavior_rules_sha256": rules_sha256,
            "risk_policy_version": risk_policy_version,
            "risk_policy_sha256": risk_policy_sha256,
            "camera_profile_id": camera_profile_id,
            "camera_profile_sha256": camera_profile_sha256,
        },
        "processing": {
            "mode": mode,
            "inference_fps": inference_fps,
            "verify_fps": verify_fps,
            "started_at": started_at,
            "finished_at": finished_at,
        },
        "artifacts": filtered_artifacts,
        "event_ids": event_ids,
    }
    return manifest


def write_manifest_file(manifest: dict[str, Any], output_path: Path) -> Path:
    """Serialize and fsync manifest.json to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    return output_path
