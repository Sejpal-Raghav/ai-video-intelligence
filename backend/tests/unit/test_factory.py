import pytest

from warehouse_ai.config import ModelBackend, Settings
from warehouse_ai.vision.adapters.replay_adapter import ReplayAdapter
from warehouse_ai.vision.adapters.ultralytics_adapter import UltralyticsAdapter
from warehouse_ai.vision.factory import _resolve_auto_device, build_detector_tracker


def test_build_detector_tracker_ultralytics_returns_ultralytics_adapter():
    settings = Settings(MODEL_BACKEND=ModelBackend.ULTRALYTICS, APP_ENV="test")

    adapter = build_detector_tracker(settings)

    assert isinstance(adapter, UltralyticsAdapter)
    # person must always be mapped; class map must not default unknown ids to package
    assert adapter._class_map.get(0) == "person"
    assert 1 not in adapter._class_map  # COCO id 1 is "bicycle", must not leak in as a class


def test_build_detector_tracker_replay_requires_no_weights(tmp_path, monkeypatch):
    tracks_path = tmp_path / "tracks.jsonl.gz"
    import gzip
    with gzip.open(tracks_path, "wt", encoding="utf-8") as f:
        f.write('{"schema_version":"track-frame.v1","frame_index":0,"timestamp_ms":0,'
                '"frame_width":1920,"frame_height":1080,"tracks":[]}\n')

    monkeypatch.setenv("REPLAY_TRACKS_PATH", str(tracks_path))
    settings = Settings(MODEL_BACKEND=ModelBackend.REPLAY, APP_ENV="test")

    adapter = build_detector_tracker(settings)

    assert isinstance(adapter, ReplayAdapter)


def test_build_detector_tracker_replay_without_env_var_raises(monkeypatch):
    monkeypatch.delenv("REPLAY_TRACKS_PATH", raising=False)
    settings = Settings(MODEL_BACKEND=ModelBackend.REPLAY, APP_ENV="test")

    with pytest.raises(FileNotFoundError):
        build_detector_tracker(settings)


def test_resolve_auto_device_returns_cpu_or_cuda():
    device = _resolve_auto_device()
    assert device in ("cpu", "cuda:0")
