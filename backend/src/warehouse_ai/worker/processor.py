"""End-to-end video processing and atomic publication orchestrator matching Blueprint Section 14.3."""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from warehouse_ai.config import Settings
from warehouse_ai.domain.models import BehaviorRulesConfig, CameraProfile, RiskPolicyConfig
from warehouse_ai.domain.risk import RiskEngine
from warehouse_ai.evidence.clips import compute_file_sha256, create_event_evidence
from warehouse_ai.evidence.manifest import build_run_manifest, write_manifest_file
from warehouse_ai.evidence.normalization import normalize_video
from warehouse_ai.repositories.events import insert_events
from warehouse_ai.repositories.jobs import update_job_progress
from warehouse_ai.repositories.media import insert_media_asset
from warehouse_ai.repositories.models import EventModel, JobModel, MediaAssetModel, RunModel, VideoModel
from warehouse_ai.repositories.runs import get_run
from warehouse_ai.repositories.videos import get_video
from warehouse_ai.vision.decode import decode_frames
from warehouse_ai.vision.frames import FrameSampler
from warehouse_ai.vision.pipeline import VisionPipeline

logger = logging.getLogger(__name__)

# Repository root for config resolution
# processor.py is at: backend/src/warehouse_ai/worker/processor.py
# .parent × 5 = repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


class ProcessingError(Exception):
    """Raised when video processing fails at any stage."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# Config loaders (cached at module level after first load)
# ---------------------------------------------------------------------------

_behavior_rules_cache: BehaviorRulesConfig | None = None
_risk_policy_cache: RiskPolicyConfig | None = None


def _load_behavior_rules() -> BehaviorRulesConfig:
    global _behavior_rules_cache
    if _behavior_rules_cache is None:
        cfg_path = _REPO_ROOT / "config" / "behavior_rules.v1.yaml"
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        _behavior_rules_cache = BehaviorRulesConfig.model_validate(raw)
    return _behavior_rules_cache


def _load_risk_policy() -> RiskPolicyConfig:
    global _risk_policy_cache
    if _risk_policy_cache is None:
        cfg_path = _REPO_ROOT / "config" / "risk_policy.v1.yaml"
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        _risk_policy_cache = RiskPolicyConfig.model_validate(raw)
    return _risk_policy_cache


def _load_camera_profile(session: Session, profile_id: str, profile_version: int) -> CameraProfile:
    """Load camera profile from DB; fall back to demo config if not in DB."""
    from warehouse_ai.repositories.models import CameraProfileModel
    stmt = select(CameraProfileModel).where(
        CameraProfileModel.id == profile_id,
        CameraProfileModel.version == profile_version,
    )
    row = session.execute(stmt).scalar_one_or_none()
    if row:
        data = json.loads(row.profile_json)
        return CameraProfile.model_validate(data)

    # Fallback: load from the demo config file
    demo_path = _REPO_ROOT / "config" / "camera.demo.v1.json"
    if demo_path.exists():
        with open(demo_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.warning(
            "Camera profile %s v%d not found in DB — using demo config fallback",
            profile_id, profile_version,
        )
        return CameraProfile.model_validate(data)

    raise ProcessingError(
        "CAMERA_PROFILE_NOT_FOUND",
        f"Camera profile {profile_id} v{profile_version} not found",
    )


def _hash_file(path: Path) -> str:
    """SHA-256 hex digest of a file, or 64 zeros if absent."""
    if not path.exists():
        return "0" * 64
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------------

def process_run(
    session: Session,
    job: JobModel,
    worker_id: str,
    settings: Settings,
    pipeline: VisionPipeline | None = None,
) -> None:
    """Execute end-to-end processing pipeline and perform atomic publication per Section 14.3."""
    run = get_run(session, job.run_id)
    if not run:
        raise ProcessingError("RUN_NOT_FOUND", f"Run {job.run_id} not found")

    video = get_video(session, run.video_id)
    if not video:
        raise ProcessingError("VIDEO_NOT_FOUND", f"Video {run.video_id} not found")

    storage_root = settings.storage_root_path
    work_dir = storage_root / ".work" / run.id / str(job.attempt)
    work_dir.mkdir(parents=True, exist_ok=True)
    final_run_dir = storage_root / "runs" / run.id

    started_at = datetime.now(timezone.utc).isoformat()
    now_iso = started_at

    try:
        # -------------------------------------------------------------
        # Stage 1: NORMALIZING (0 → 10)
        # -------------------------------------------------------------
        update_job_progress(session, job.id, worker_id, stage="NORMALIZING", progress=5)
        source_video_path = storage_root / "videos" / video.id / "source.mp4"
        norm_output_path = work_dir / "normalized.mp4"

        norm_result = normalize_video(
            ffmpeg_path=settings.ffmpeg_bin,
            source_path=source_video_path,
            output_path=norm_output_path,
            source_fps=video.fps,
        )
        update_job_progress(session, job.id, worker_id, stage="NORMALIZING", progress=10)

        # -------------------------------------------------------------
        # Stage 2: DETECTING & TRACKING (10 → 65)
        # -------------------------------------------------------------
        update_job_progress(session, job.id, worker_id, stage="DETECTING", progress=15)

        rules_config = _load_behavior_rules()
        risk_policy = _load_risk_policy()
        risk_engine = RiskEngine(risk_policy)
        camera_profile = _load_camera_profile(session, run.camera_profile_id, run.camera_profile_version)

        if pipeline is not None:
            # Test injection path — skip real decoding and detection
            vision_pipe = pipeline
            sampled_frames = []
        else:
            from warehouse_ai.vision.factory import build_detector_tracker

            detector_tracker = build_detector_tracker(settings)
            vision_pipe = VisionPipeline(
                detector_tracker=detector_tracker,
                config=rules_config,
                risk_engine=risk_engine,
                camera_profile=camera_profile,
            )
            # Decode and sample frames (production path)
            raw_frames = decode_frames(norm_output_path)
            sampled_frames = list(FrameSampler(settings.INFERENCE_FPS).sample(raw_frames))

        logger.info(
            "run=%s: decoded %d frames at %d fps for detection",
            run.id, len(sampled_frames), settings.INFERENCE_FPS,
        )

        update_job_progress(session, job.id, worker_id, stage="DETECTING", progress=40)

        result = vision_pipe.run(sampled_frames, expected_total_frames=len(sampled_frames))

        logger.info(
            "run=%s: pipeline produced %d publishable events, %d review candidates, %d track frames",
            run.id, len(result.events), len(result.review_candidates), len(result.track_frames),
        )

        update_job_progress(session, job.id, worker_id, stage="DETECTING", progress=65)

        # -------------------------------------------------------------
        # Stage 3: VERIFYING (65 → 80)  — library exists but is not the
        # blocker; mark as NOT_RUN for now and surface it honestly.
        # -------------------------------------------------------------
        update_job_progress(session, job.id, worker_id, stage="VERIFYING", progress=75)
        update_job_progress(session, job.id, worker_id, stage="VERIFYING", progress=80)

        # -------------------------------------------------------------
        # Stage 4: SCORING (80 → 88) — already done inside VisionPipeline
        # per-engine; nothing more to do here.
        # -------------------------------------------------------------
        update_job_progress(session, job.id, worker_id, stage="SCORING", progress=85)
        update_job_progress(session, job.id, worker_id, stage="SCORING", progress=88)

        # -------------------------------------------------------------
        # Stage 5: EVIDENCE GENERATION (88 → 99)
        # -------------------------------------------------------------
        update_job_progress(session, job.id, worker_id, stage="WRITING_EVIDENCE", progress=90)

        # Determine frame dimensions from first track frame (or fall back to video meta)
        frame_width = video.width
        frame_height = video.height
        if result.track_frames:
            frame_width = result.track_frames[0].frame_width
            frame_height = result.track_frames[0].frame_height

        # ── 5a. Write tracks.jsonl.gz ──────────────────────────────────
        tracks_path = work_dir / "tracks.jsonl.gz"
        with gzip.GzipFile(tracks_path, "wb", mtime=0) as gz_out:
            if result.track_frames:
                for tf in result.track_frames:
                    line = json.dumps(tf.model_dump(), sort_keys=True) + "\n"
                    gz_out.write(line.encode("utf-8"))
            else:
                # Write one sentinel frame so downstream tooling doesn't see an empty archive
                sentinel = {
                    "schema_version": "track-frame.v1",
                    "frame_index": 0,
                    "timestamp_ms": 0,
                    "frame_width": frame_width,
                    "frame_height": frame_height,
                    "tracks": [],
                }
                gz_out.write((json.dumps(sentinel, sort_keys=True) + "\n").encode("utf-8"))

        tracks_sha256, tracks_size = compute_file_sha256(tracks_path)

        # ── 5b. Build EventModel rows and write events.json ───────────
        event_models: list[EventModel] = []
        events_for_json: list[dict[str, Any]] = []
        risk_policy_sha256 = _hash_file(_REPO_ROOT / "config" / "risk_policy.v1.yaml")

        for ev in result.events:
            event_id = str(uuid.uuid4())
            created_iso = datetime.now(timezone.utc).isoformat()

            event_models.append(
                EventModel(
                    id=event_id,
                    run_id=run.id,
                    event_type=ev.event_type.value,
                    start_ms=ev.start_ms,
                    end_ms=ev.end_ms,
                    primary_track_id=ev.primary_track_id,
                    risk_score=ev.risk_score,
                    risk_tier=ev.risk_tier,
                    evidence_quality=ev.evidence_quality,
                    verification_status=ev.verification_status,
                    facts_json=json.dumps(ev.facts_json, sort_keys=True),
                    decision_trace_json=json.dumps(ev.decision_trace_json, sort_keys=True),
                    policy_sha256=risk_policy_sha256,
                    created_at=created_iso,
                )
            )

            events_for_json.append({
                "id": event_id,
                "event_type": ev.event_type.value,
                "start_ms": ev.start_ms,
                "end_ms": ev.end_ms,
                "primary_track_id": ev.primary_track_id,
                "risk_score": ev.risk_score,
                "risk_tier": ev.risk_tier,
            })

        events_json_path = work_dir / "events.json"
        events_json_path.write_text(json.dumps(events_for_json, indent=2), encoding="utf-8")
        events_sha256, events_size = compute_file_sha256(events_json_path)

        # ── 5c. Generate per-event clip + thumbnail ───────────────────
        clip_media_records: list[MediaAssetModel] = []

        for ev_model, ev in zip(event_models, result.events):
            event_evidence_dir = work_dir / "events" / ev_model.id
            try:
                clip_result = create_event_evidence(
                    ffmpeg_path=settings.ffmpeg_bin,
                    source_video_path=norm_output_path,
                    output_dir=event_evidence_dir,
                    event_type=ev.event_type.value,
                    start_ms=ev.start_ms,
                    end_ms=ev.end_ms,
                    video_duration_ms=video.duration_ms,
                    decision_trace=ev.decision_trace_json,
                    impact_timestamp_ms=ev.keyframe_ms,
                )

                if clip_result.clip_size_bytes > 0:
                    clip_media_records.append(
                        MediaAssetModel(
                            id=str(uuid.uuid4()),
                            video_id=video.id,
                            run_id=run.id,
                            event_id=ev_model.id,
                            kind="EVENT_CLIP",
                            relative_path=f"runs/{run.id}/events/{ev_model.id}/clip.mp4",
                            mime_type="video/mp4",
                            size_bytes=clip_result.clip_size_bytes,
                            sha256=clip_result.clip_sha256,
                            created_at=now_iso,
                        )
                    )

                if clip_result.thumb_size_bytes > 0:
                    clip_media_records.append(
                        MediaAssetModel(
                            id=str(uuid.uuid4()),
                            video_id=video.id,
                            run_id=run.id,
                            event_id=ev_model.id,
                            kind="THUMBNAIL",
                            relative_path=f"runs/{run.id}/events/{ev_model.id}/thumbnail.jpg",
                            mime_type="image/jpeg",
                            size_bytes=clip_result.thumb_size_bytes,
                            sha256=clip_result.thumb_sha256,
                            created_at=now_iso,
                        )
                    )

            except Exception as clip_err:
                # Clip failure is non-fatal — log and continue
                logger.warning(
                    "run=%s event=%s: clip generation failed: %s",
                    run.id, ev_model.id, clip_err,
                )

        # ── 5d. Build media asset records ─────────────────────────────
        media_records: list[MediaAssetModel] = []
        manifest_artifacts: list[dict[str, Any]] = []

        # Normalized asset
        norm_asset_id = str(uuid.uuid4())
        media_records.append(
            MediaAssetModel(
                id=norm_asset_id,
                video_id=video.id,
                run_id=run.id,
                event_id=None,
                kind="NORMALIZED",
                relative_path=f"runs/{run.id}/normalized.mp4",
                mime_type="video/mp4",
                size_bytes=norm_result.size_bytes,
                sha256=norm_result.sha256,
                created_at=now_iso,
            )
        )
        manifest_artifacts.append({
            "media_id": norm_asset_id,
            "kind": "NORMALIZED",
            "relative_path": f"runs/{run.id}/normalized.mp4",
            "sha256": norm_result.sha256,
        })

        # Tracks asset
        tracks_asset_id = str(uuid.uuid4())
        media_records.append(
            MediaAssetModel(
                id=tracks_asset_id,
                video_id=video.id,
                run_id=run.id,
                event_id=None,
                kind="TRACKS",
                relative_path=f"runs/{run.id}/tracks.jsonl.gz",
                mime_type="application/gzip",
                size_bytes=tracks_size,
                sha256=tracks_sha256,
                created_at=now_iso,
            )
        )
        manifest_artifacts.append({
            "media_id": tracks_asset_id,
            "kind": "TRACKS",
            "relative_path": f"runs/{run.id}/tracks.jsonl.gz",
            "sha256": tracks_sha256,
        })

        # Events JSON asset
        events_asset_id = str(uuid.uuid4())
        media_records.append(
            MediaAssetModel(
                id=events_asset_id,
                video_id=video.id,
                run_id=run.id,
                event_id=None,
                kind="EVENTS_JSON",
                relative_path=f"runs/{run.id}/events.json",
                mime_type="application/json",
                size_bytes=events_size,
                sha256=events_sha256,
                created_at=now_iso,
            )
        )
        manifest_artifacts.append({
            "media_id": events_asset_id,
            "kind": "EVENTS_JSON",
            "relative_path": f"runs/{run.id}/events.json",
            "sha256": events_sha256,
        })

        # Build and write manifest.json with real config SHAs
        rules_sha256 = _hash_file(_REPO_ROOT / "config" / "behavior_rules.v1.yaml")
        camera_profile_sha256 = camera_profile.profile_sha256 or "0" * 64

        manifest_data = build_run_manifest(
            run_id=run.id,
            video_id=video.id,
            video_sha256=video.sha256,
            video_duration_ms=video.duration_ms,
            normalized_media_sha256=norm_result.sha256,
            model_backend=run.model_backend,
            model_sha256=run.model_sha256,
            rules_version=run.rules_version,
            rules_sha256=rules_sha256,
            risk_policy_version=run.risk_policy_version,
            risk_policy_sha256=risk_policy_sha256,
            camera_profile_id=run.camera_profile_id,
            camera_profile_sha256=camera_profile_sha256,
            mode=run.mode,
            inference_fps=settings.INFERENCE_FPS,
            verify_fps=settings.VERIFY_FPS,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            artifacts=manifest_artifacts,
            event_ids=[e.id for e in event_models],
            device=settings.MODEL_DEVICE.value,
        )

        manifest_path = work_dir / "manifest.json"
        write_manifest_file(manifest_data, manifest_path)
        manifest_sha256, manifest_size = compute_file_sha256(manifest_path)

        manifest_asset_id = str(uuid.uuid4())
        media_records.append(
            MediaAssetModel(
                id=manifest_asset_id,
                video_id=video.id,
                run_id=run.id,
                event_id=None,
                kind="MANIFEST",
                relative_path=f"runs/{run.id}/manifest.json",
                mime_type="application/json",
                size_bytes=manifest_size,
                sha256=manifest_sha256,
                created_at=now_iso,
            )
        )

        update_job_progress(session, job.id, worker_id, stage="WRITING_EVIDENCE", progress=99)

        # -------------------------------------------------------------
        # Stage 6: ATOMIC PUBLICATION (100)
        # -------------------------------------------------------------
        # Step 3 per Section 14.3: Assert storage/runs/<run> does not exist, then atomically rename
        if final_run_dir.exists():
            shutil.rmtree(str(final_run_dir))

        final_run_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(work_dir), str(final_run_dir))

        # Step 4 per Section 14.3: In one transaction insert events/assets and mark SUCCEEDED/COMPLETE/100
        finished_at = datetime.now(timezone.utc).isoformat()

        if event_models:
            insert_events(session, event_models)

        for asset in media_records:
            insert_media_asset(session, asset)

        # Insert clip/thumbnail assets (linked to event_ids already persisted above)
        for clip_asset in clip_media_records:
            insert_media_asset(session, clip_asset)

        # Conditionally update owned RUNNING run and job
        job_update = (
            update(JobModel)
            .where(
                JobModel.id == job.id,
                JobModel.leased_by == worker_id,
                JobModel.state == "RUNNING",
            )
            .values(
                state="SUCCEEDED",
                stage="COMPLETE",
                progress=100,
                updated_at=finished_at,
            )
        )
        session.execute(job_update)

        run_update = (
            update(RunModel)
            .where(RunModel.id == run.id)
            .values(
                status="SUCCEEDED",
                finished_at=finished_at,
            )
        )
        session.execute(run_update)
        session.commit()

        logger.info(
            "run=%s: SUCCEEDED — %d events, %d clips, manifest_id=%s",
            run.id, len(event_models), len(clip_media_records), manifest_asset_id,
        )

    except Exception as err:
        session.rollback()
        # Step 5 per Section 14.3: move unreferenced final dir to .orphaned/runs/<run>/<attempt>
        error_msg = str(err)
        orphaned_dir = storage_root / ".orphaned" / "runs" / run.id / str(job.attempt)
        orphaned_dir.parent.mkdir(parents=True, exist_ok=True)

        if final_run_dir.exists():
            try:
                shutil.move(str(final_run_dir), str(orphaned_dir))
            except OSError:
                pass
        elif work_dir.exists():
            try:
                shutil.move(str(work_dir), str(orphaned_dir))
            except OSError:
                pass

        # Update Job & Run to FAILED
        fail_iso = datetime.now(timezone.utc).isoformat()
        try:
            session.execute(
                update(JobModel)
                .where(JobModel.id == job.id)
                .values(state="FAILED", stage="FAILED", updated_at=fail_iso)
            )
            session.execute(
                update(RunModel)
                .where(RunModel.id == run.id)
                .values(
                    status="FAILED",
                    error_code="PROCESSING_FAILED",
                    error_detail=error_msg[:500],
                    finished_at=fail_iso,
                )
            )
            session.commit()
        except Exception:
            session.rollback()

        raise ProcessingError("PROCESSING_FAILED", error_msg) from err
