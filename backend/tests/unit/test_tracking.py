import tempfile
from pathlib import Path
import pytest

from warehouse_ai.domain.models import TrackFrame, TrackObservation
from warehouse_ai.vision.tracking import (
    interpolate_tracks,
    read_canonical_tracks,
    write_canonical_tracks,
)


def test_gap_interpolation():
    # Track appears at 0ms and 200ms (gap 200ms, frame at 100ms missing track)
    f0 = TrackFrame(
        frame_index=0,
        timestamp_ms=0,
        frame_width=1920,
        frame_height=1080,
        tracks=[
            TrackObservation(
                track_id=1,
                class_id="package",
                confidence=0.8,
                bbox_xyxy_norm=(0.1, 0.1, 0.2, 0.2),
            )
        ],
    )
    f1 = TrackFrame(
        frame_index=1,
        timestamp_ms=100,
        frame_width=1920,
        frame_height=1080,
        tracks=[],  # Missing track 1
    )
    f2 = TrackFrame(
        frame_index=2,
        timestamp_ms=200,
        frame_width=1920,
        frame_height=1080,
        tracks=[
            TrackObservation(
                track_id=1,
                class_id="package",
                confidence=0.9,
                bbox_xyxy_norm=(0.3, 0.3, 0.4, 0.4),
            )
        ],
    )

    interpolated = interpolate_tracks([f0, f1, f2], max_gap_ms=200)
    assert len(interpolated[1].tracks) == 1
    mid_obs = interpolated[1].tracks[0]
    assert mid_obs.is_interpolated is True
    assert mid_obs.track_id == 1
    # Check linear interpolation mid-points
    assert mid_obs.bbox_xyxy_norm == (0.2, 0.2, 0.3, 0.3)
    assert mid_obs.confidence == 0.85


def test_large_gap_not_interpolated():
    # Gap of 300 ms exceeds 200 ms limit
    f0 = TrackFrame(
        frame_index=0,
        timestamp_ms=0,
        frame_width=1920,
        frame_height=1080,
        tracks=[
            TrackObservation(
                track_id=1,
                class_id="package",
                confidence=0.8,
                bbox_xyxy_norm=(0.1, 0.1, 0.2, 0.2),
            )
        ],
    )
    f1 = TrackFrame(
        frame_index=1,
        timestamp_ms=150,
        frame_width=1920,
        frame_height=1080,
        tracks=[],
    )
    f2 = TrackFrame(
        frame_index=2,
        timestamp_ms=300,
        frame_width=1920,
        frame_height=1080,
        tracks=[
            TrackObservation(
                track_id=1,
                class_id="package",
                confidence=0.8,
                bbox_xyxy_norm=(0.3, 0.3, 0.4, 0.4),
            )
        ],
    )

    interpolated = interpolate_tracks([f0, f1, f2], max_gap_ms=200)
    assert len(interpolated[1].tracks) == 0


def test_canonical_gzip_reproducibility():
    f0 = TrackFrame(
        frame_index=0,
        timestamp_ms=0,
        frame_width=1920,
        frame_height=1080,
        tracks=[
            TrackObservation(
                track_id=2,
                class_id="pallet",
                confidence=0.9,
                bbox_xyxy_norm=(0.1, 0.6, 0.5, 0.9),
            ),
            TrackObservation(
                track_id=1,
                class_id="package",
                confidence=0.85,
                bbox_xyxy_norm=(0.2, 0.3, 0.4, 0.5),
            ),
        ],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = Path(tmpdir) / "tracks1.jsonl.gz"
        p2 = Path(tmpdir) / "tracks2.jsonl.gz"

        write_canonical_tracks([f0], p1)
        write_canonical_tracks([f0], p2)

        # Byte-identical outputs check (gzip mtime=0 and sorted keys)
        with open(p1, "rb") as f1, open(p2, "rb") as f2:
            assert f1.read() == f2.read()

        # Read back test
        read_frames = read_canonical_tracks(p1)
        assert len(read_frames) == 1
        assert read_frames[0].timestamp_ms == 0
        # Tracks sorted by (class_id, track_id)
        assert read_frames[0].tracks[0].class_id == "package"
        assert read_frames[0].tracks[1].class_id == "pallet"
