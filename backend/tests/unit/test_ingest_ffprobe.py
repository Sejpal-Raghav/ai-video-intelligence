"""Regression test for run_ffprobe() against a REAL video file with a real
ffprobe subprocess — no mocking.

This exact gap (no test ever invoked run_ffprobe for real) is why a total,
100%-reproducing bug went undetected: this ffmpeg 8.1.1 (gyan.dev Windows)
build fails every single ffprobe call that passes the -nostdin flag,
because it parses -nostdin as taking a value and consumes the next argument
(the file path) as that value, then fails with "Option not found". Every
video upload was silently broken until this was found and fixed (stdin is
now closed via subprocess's own stdin=DEVNULL instead of the CLI flag).
"""
import shutil

import pytest

from warehouse_ai.services.ingest import run_ffprobe


def _ffprobe_available() -> str | None:
    return shutil.which("ffprobe")


@pytest.mark.skipif(_ffprobe_available() is None, reason="ffprobe not on PATH in this environment")
def test_run_ffprobe_real_invocation_succeeds(tmp_path):
    import cv2
    import numpy as np

    video_path = tmp_path / "probe_test.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 25.0, (64, 48))
    for i in range(25):
        writer.write(np.full((48, 64, 3), fill_value=i % 256, dtype=np.uint8))
    writer.release()

    ffprobe_path = _ffprobe_available()
    result = run_ffprobe(ffprobe_path, video_path)

    assert "format" in result
    assert "streams" in result
    video_streams = [s for s in result["streams"] if s.get("codec_type") == "video"]
    assert len(video_streams) == 1
    assert video_streams[0]["width"] == 64
    assert video_streams[0]["height"] == 48
