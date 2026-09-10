# Replay-mode demo fixture

This directory contains a deterministic, hand-authored demonstration fixture
for `MODEL_BACKEND=replay`, used because the live COCO-proxy detector
(`MODEL_BACKEND=ultralytics`, see `docs/model_card.md` Section 0) does not
reliably clear the rule engines' motion/duration thresholds on the raw
warehouse footage in `data/video/`.

## Files

- `throwing-mattresses-demo-clip.mp4` — the first 2.5 seconds of
  `data/video/Throwing Mattresses.mp4`, trimmed with `ffmpeg -t 2.5` so the
  clip's entire sampled-frame span matches the fixture below exactly (no
  "empty detection" tail after the sequence — see the note below on why that
  matters).
- `throwing-mattresses.tracks.jsonl.gz` — pre-tracked `TrackFrame` records
  for every 10fps-sampled frame of that clip, following the exact proven
  drop-sequence phase pattern from
  `backend/tests/unit/test_pipeline.py::test_vision_pipeline_end_to_end`
  (controlled → released → rapid downward motion → impact → settled).

## What this demonstrates

Run `process_run()` with `MODEL_BACKEND=replay` and
`REPLAY_TRACKS_PATH=data/replay/throwing-mattresses.tracks.jsonl.gz` against
`throwing-mattresses-demo-clip.mp4` and the full, real, unmodified pipeline
(`VisionPipeline` → `HeroStateMachine` → `RiskEngine` → `evidence/clips.py`)
produces a genuine `DROP` event (risk tier `HIGH`, score 70), a real
evidence clip, and a real thumbnail cut from actual video frames — verified
by `backend/tests/integration/test_replay_fixture.py`.

**This is not a claim that the system correctly detected a drop in this
specific footage from pixels.** The track data here is authored, not
detected — it exists to demonstrate that everything *downstream* of
detection (temporal reasoning, risk scoring, evidence generation, the API,
and the review workflow) is real, correct, and working end-to-end, which is
otherwise very hard to verify given the live detector's limited recall on
this footage. See `docs/model_card.md` Section 0 for the honest, measured
comparison between the two paths.

## Why the clip had to be trimmed

`ReplayAdapter` looks up detections by exact `timestamp_ms` and returns an
**empty** detection list for any sampled frame not present in the fixture.
The original attempt used the full ~42-second source video with a fixture
covering only its first 1.5 seconds — the ~400 subsequent frames of "no
detection" prevented `HeroStateMachine` from ever reaching its `EMIT` state,
even though the interesting 1.5-second window was correct in isolation. Once
the source clip was trimmed to match the fixture's actual span, the event
fired correctly.
