import numpy as np
import pytest
import cv2

from warehouse_ai.vision.decode import decode_frames
from warehouse_ai.vision.frames import FrameSampler


def _write_synthetic_video(path, num_frames: int, fps: float, size=(64, 48)) -> None:
    width, height = size
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    assert writer.isOpened(), "failed to open cv2.VideoWriter for synthetic test video"
    for i in range(num_frames):
        frame = np.full((height, width, 3), fill_value=i % 256, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def test_decode_frames_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        list(decode_frames(tmp_path / "does-not-exist.mp4"))


def test_decode_frames_yields_all_frames_in_order(tmp_path):
    video_path = tmp_path / "synthetic.mp4"
    _write_synthetic_video(video_path, num_frames=30, fps=30.0)

    frames = list(decode_frames(video_path))

    assert len(frames) == 30
    # Frame indices are sequential starting at 0
    assert [f.index for f in frames] == list(range(30))
    # Timestamps are monotonically non-decreasing
    timestamps = [f.timestamp_ms for f in frames]
    assert timestamps == sorted(timestamps)
    # Each frame carries real decoded image data of the expected shape
    assert frames[0].bgr.shape == (48, 64, 3)


def test_decode_frames_then_sample_reduces_to_target_fps(tmp_path):
    video_path = tmp_path / "synthetic_30fps.mp4"
    _write_synthetic_video(video_path, num_frames=60, fps=30.0)

    sampled = list(FrameSampler(target_fps=10).sample(decode_frames(video_path)))

    # 60 frames at 30fps = 2s of video; sampled at 10fps should yield ~20 frames
    assert 18 <= len(sampled) <= 22
    # Sampled timestamps should be spaced roughly 100ms apart
    gaps = [b.timestamp_ms - a.timestamp_ms for a, b in zip(sampled, sampled[1:])]
    assert all(80 <= gap <= 120 for gap in gaps)
