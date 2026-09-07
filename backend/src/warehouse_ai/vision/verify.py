from typing import Iterable, Sequence

from warehouse_ai.domain.enums import VerificationStatus
from warehouse_ai.domain.models import BehaviorRulesConfig, Frame, TrackObservation
from warehouse_ai.domain.risk import RiskEngine
from warehouse_ai.vision.adapters.base import DetectorTracker
from warehouse_ai.vision.candidates import compute_spatial_box_iou, compute_temporal_iou
from warehouse_ai.vision.features import extract_track_kinematics
from warehouse_ai.vision.rules.drop_forceful_release import EmittedHeroEvent, HeroStateMachine


def verify_hero_candidate(
    first_pass_event: EmittedHeroEvent,
    first_pass_observations: Sequence[TrackObservation],
    verifier_frames: Iterable[Frame],
    detector_tracker: DetectorTracker,
    config: BehaviorRulesConfig,
    risk_engine: RiskEngine,
) -> tuple[EmittedHeroEvent, VerificationStatus]:
    """Run candidate-to-verifier cascade on candidate window at high FPS (Section 10.5)."""
    try:
        frames_list = list(verifier_frames)
        if not frames_list:
            return first_pass_event, VerificationStatus.FAILED

        # Run detector-tracker on verifier frames from clean state
        track_seqs = list(detector_tracker.process(frames_list))

        # Group observations by track_id
        candidate_boxes_by_time = {
            f.timestamp_ms: obs.bbox_xyxy_norm
            for f, obs in zip(frames_list, first_pass_observations, strict=False)
            if obs.bbox_xyxy_norm is not None
        }

        verifier_tracks: dict[int, list[tuple[int, TrackObservation]]] = {}
        for frame, detections in zip(frames_list, track_seqs, strict=False):
            for det in detections:
                if det.class_id == "package":
                    obs = TrackObservation(
                        track_id=det.track_id,
                        class_id=det.class_id,
                        confidence=det.confidence,
                        bbox_xyxy_norm=det.bbox_xyxy_norm,
                        is_interpolated=det.is_interpolated,
                    )
                    verifier_tracks.setdefault(det.track_id, []).append((frame.timestamp_ms, obs))

        # Find best matching verifier track: temporal-IoU >= 0.50 and mean spatial IoU >= 0.30
        best_track_id: int | None = None
        best_overlap_score = 0.0

        fp_start = first_pass_event.start_ms
        fp_end = first_pass_event.end_ms

        for tr_id, tr_obs_list in verifier_tracks.items():
            t_min = tr_obs_list[0][0]
            t_max = tr_obs_list[-1][0]

            temp_iou = compute_temporal_iou(fp_start, fp_end, t_min, t_max)
            if temp_iou < 0.50:
                continue

            # Compute mean spatial IoU over overlapping timestamps
            spatial_ious: list[float] = []
            for t_ms, obs in tr_obs_list:
                if t_ms in candidate_boxes_by_time:
                    s_iou = compute_spatial_box_iou(obs.bbox_xyxy_norm, candidate_boxes_by_time[t_ms])
                    spatial_ious.append(s_iou)

            mean_s_iou = (sum(spatial_ious) / len(spatial_ious)) if spatial_ious else 0.0
            if mean_s_iou >= 0.30:
                combined_score = temp_iou + mean_s_iou
                if combined_score > best_overlap_score:
                    best_overlap_score = combined_score
                    best_track_id = tr_id

        if best_track_id is None:
            # No matching track verified: retain first-pass result with FAILED verification status
            return first_pass_event, VerificationStatus.FAILED

        # Re-evaluate Hero state machine on the matched verifier track
        matched_obs_list = verifier_tracks[best_track_id]
        timestamps = [item[0] for item in matched_obs_list]
        observations = [item[1] for item in matched_obs_list]

        kinematics = extract_track_kinematics(observations, timestamps)
        sm = HeroStateMachine(best_track_id, config, risk_engine)

        verified_event: EmittedHeroEvent | None = None
        for kin, obs in zip(kinematics, observations, strict=False):
            res = sm.update(
                kin=kin,
                raw_obs=obs,
                is_handled_or_supported=False,  # Evaluated in verifier window
                is_on_floor_or_supported=False,
                all_track_observations=observations,
                expected_frames_window=len(frames_list),
            )
            if res is not None:
                verified_event = res
                break

        if verified_event is not None:
            return verified_event, VerificationStatus.PASSED

        return first_pass_event, VerificationStatus.FAILED

    except Exception:
        # Error during verification routes to human review with FAILED status
        return first_pass_event, VerificationStatus.FAILED
