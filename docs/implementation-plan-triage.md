# AI Video Intelligence for Warehouse Handling — Triage Implementation Plan

> **For the implementing session:** Read this file top to bottom before touching code. It contains the
> full assignment requirements and a verified repository analysis. You should not need to re-read the
> .docx or re-explore the repo.

---

## 1. Executive Summary

**The situation.** This repo is a hackathon submission for the Godrej "AI Video Intelligence for
Warehouse Handling" challenge. The stated submission deadline in the assignment document is
**10 September 2026 — today**. The user has confirmed: **hours remain, triage only.**

**The core finding.** The repository looks far more complete than it is. It has an excellent
deterministic vision/rules/risk *library*, a clean FastAPI surface, a real job/worker/lease system,
strong DB constraints, an evidence/clip module and an offline evaluation harness. **But the worker
that connects them is a stub.** `backend/src/warehouse_ai/worker/processor.py:84-93` builds a
`FallbackPipeline` and **never calls `.run()` on it at all**; line 129 hardcodes
`events.json = "[]"`. There is **no frame decoder**, **no adapter factory**, and **no model weights**
(`models/warehouse-v1.pt` is absent; its recorded SHA-256 is `e3b0c442…b855`, the hash of the empty
string). Consequently **the shipped system always produces zero events**. Every downstream feature —
event list, timeline, risk badges, review workflow, analytics — is real code rendering an empty set.

**What this plan does.** It restores one honest end-to-end path — real warehouse video in, real
detections, real tracked behaviour events, real risk scores, visible evidence on screen — then adds
the two highest-rubric-value features that are currently 0% built (grounded assistant, object
overlay), and explicitly reserves time for the deck and demo video, which are worth 15% and are the
actual submission artifact.

**Confirmed decisions (from the user):**

| Fork | Decision |
|---|---|
| Time budget | Hours left today — **triage only** |
| Detector | **Pretrained COCO YOLO + class mapping** (`pip install ultralytics`, stock `yolo11n`) |
| Assistant | **Deterministic grounded assistant, no LLM** (no API key, cannot hallucinate) |
| ≥10 behaviours | **Both** — lead with blueprint's "3 engines × 10 scenarios" framing; add detectors only if time allows |

**Assets that make this achievable:** `data/video/` contains **7 real warehouse MP4s (~210 MB)** whose
filenames name ~10 of the required behaviours. `cv2` (opencv-python-headless 4.10.0) is already
installed. `evidence/clips.py`, `domain/risk.py`, `vision/pipeline.py` and all three rule engines are
real, tested, working code that just needs to be *called*.

---

## 2. Detailed Problem Statement

**Problem.** Warehouses damage product during loading/unloading not mainly through equipment failure
but through **handling behaviour**: dropping, dragging, throwing, improper/unstable stacking,
excessive force, wrong orientation, unsupported placement, using straps as handles, stepping on
cartons, handling without correct equipment. Traditional CCTV only *records* — damage is discovered
afterwards, during investigation.

**Required system.** An AI + Computer Vision "Field Intelligence Assistant" that converts existing
warehouse cameras or smartphone cameras into an operational assistant. It must shift the workflow
from `Camera → Recording → Human review → Incident discovered → Corrective action` to
`Camera → AI perception → Behaviour understanding → Risk detection → Alert → Intervention → Learning`.
The emphasis is explicitly **proactive prevention, not retrospective monitoring**.

**Intended users.** Warehouse supervisor (primary), loading/unloading operator, logistics manager,
quality professional, safety professional.

**Inputs.** Warehouse loading/unloading video — existing CCTV footage, recorded warehouse video,
smartphone-recorded video, simulated environments, or synthetic/public footage. Pilot videos are
supplied via a Google Drive link; **equivalents already exist in `data/video/`**.

**Required processing.** The brief is explicit that this must exceed object detection:
`Object Detection + Object Tracking + Action Recognition + Temporal Reasoning + Risk Classification`.
It must "detect sequence of actions rather than individual frames." The worked example given is:
*operator picks up product → moves product → product is dropped → impact event detected → product
remains stationary → potential damage event identified.*

**Required outputs.** Per-event: behaviour label, risk level (Low/Medium/High/Critical), timestamp,
evidence, explanation of *why* it is risky, and a recommended corrective action. Aggregate: event
timeline, dashboard, risk categories, daily/shift summaries, behaviour trends.

**Critical constraint — responsible AI.** The system must distinguish
**Observed behaviour → Potential risk → Confirmed damage** and must *not* claim damage occurred
without sufficient evidence. It must focus on process improvement, not employee surveillance: no
employee rankings, no automated punitive decisions, no face identity. Privacy, consent, data
minimization, retention, role-based access, human review of significant incidents, false-positive
management and explainability are all called out.

**Technologies.** Not mandated. Suggested stack areas for the deck: computer vision, AI/ML, LLM,
video processing, edge/cloud, front-end, data storage.

---

## 3. Complete Requirements Breakdown

### 3.1 Functional Requirements

| # | Requirement | Source |
|---|---|---|
| F1 | Ingest live or recorded video | Expected Solution §1 |
| F2 | Detect people, products, pallets and equipment | §1 |
| F3 | Identify loading/unloading activities | §1 |
| F4 | Track objects across frames | §1 |
| F5 | Detect handling behaviours (dropping, dragging, throwing, improper stacking…) | §2 |
| F6 | Distinguish normal from potentially damaging behaviour | §2 |
| F7 | Detect **sequences** of actions, not single frames | §2 |
| F8 | Assign a risk level; identify high-risk events | §3 |
| F9 | Generate event timestamp + evidence | §3 |
| F10 | AI assistant: explain what happened | §4 |
| F11 | AI assistant: explain **why** the behaviour is risky | §4 |
| F12 | AI assistant: answer questions about incidents | §4 |
| F13 | AI assistant: recommend corrective actions | §4 |
| F14 | AI assistant: summarize shift-level observations | §4 |
| F15 | Highlight detected event on video | §5 |
| F16 | Display risk category | §5 |
| F17 | Show event timeline | §5 |
| F18 | Generate daily/shift summaries | §5 |
| F19 | Provide behaviour trends | §5 |
| F20 | Identify recurring behaviours | §6 |
| F21 | Recommend training opportunities | §6 |
| F22 | Highlight high-risk locations/processes | §6 |
| F23 | Track improvement over time | §6 |
| F24 | Demonstrate **≥10 predefined behaviours/scenarios** | Submission Req. §1 |

> **Note the internal inconsistency in the brief:** SCOPE says "A minimum of 4/5 behaviours or
> scenarios should be demonstrated", Submission Requirements §1 says "at least 10 predefined
> behaviours/scenarios". **Plan for 10** — it is the stricter and later statement.

### 3.2 Non-Functional Requirements
- Real-time or **near-real-time** alerting (brief allows either).
- Detection latency is a listed success metric.
- False-positive rate is a listed success metric and a Responsible-AI concern.
- Prototype must be demonstrable on a laptop (controlled/simulated environment explicitly allowed).
- Secure video storage; appropriate retention periods.

### 3.3 Technical Requirements
- Platform-agnostic application (native or web).
- Object detection + tracking + action recognition + temporal reasoning + risk classification.
- Deck must name the stack for: CV, AI/ML, LLM, video processing, edge/cloud, front-end, storage.

### 3.4 Input Requirements
- Warehouse loading/unloading video; any of CCTV / recorded / smartphone / simulated / synthetic.
- Where real footage is used: privacy, authorization, responsible use of employee data.

### 3.5 Output Requirements
- Per-event: behaviour label, risk tier, timestamp, evidence, explanation, recommendation.
- Dashboard: timeline, risk categories, daily/shift summaries, behaviour trends.
- Incident replay.
- Deck (5–6 slides) + demo video covering 3–5 representative scenarios.

### 3.6 Constraints
- **Must not** claim damage occurred without sufficient evidence.
- **Must not** become indiscriminate employee surveillance.
- **Must not** make automated punitive decisions.
- Assistant **must** answer from detected events, **not invent information**.
- Team size 3–5.

### 3.7 Evaluation Requirements
Judging weights: Innovation & Creativity 15%, Technical Execution 20%, AI + Video Intelligence
Integration 20%, User Experience & User Feedback 10%, Damage Prevention & Business Impact 20%,
Presentation Quality 15%.

---

## 4. Detailed Marking Criteria Analysis

| Criterion | Marks | What Full Marks Require | Current Evidence | Status | Missing Work |
|---|---:|---|---|---|---|
| **Innovation & Creativity** | 15% | Beyond object detection: temporal reasoning, proof-carrying decision trace, prevention framing, novel assistant | `HeroStateMachine` FSM (`drop_forceful_release.py:13-19`), `DecisionTrace` (`domain/decision_trace.py`), quality gate (`rules/base.py:29-118`) — genuinely differentiated design | 🟡 | Nothing runs end to end, so none of it is *demonstrable*. Assistant absent. |
| **Technical Execution** | 20% | Working prototype, clean architecture, tests passing, real inference | 47 backend tests pass; strong DB constraints; RFC7807; job/lease worker | 🟡 | `process_run` stubbed → zero events. No weights, decoder, or adapter factory. |
| **AI + Video Intelligence Integration** | 20% | Detection→tracking→action→temporal→risk actually wired and shown on real footage | Every stage exists as a tested library; **none are connected** | ❌ | The entire P0 critical path below. |
| **User Experience & User Feedback** | 10% | Judge can drive the app; incident replay; documented user validation | Upload flow, run page + `Timeline.tsx`, append-only review workflow are good | 🟡 | Event video 404s; no bbox overlay; no incident replay; no user-feedback documentation. |
| **Damage Prevention & Business Impact** | 20% | Prevention narrative + quantified impact metrics | `evaluation.py` computes P/R/F1 + false-alert rate; risk explanations are prevention-oriented | 🟡 | Never surfaced in UI/API; no shift summary; no impact metrics slide. |
| **Presentation Quality** | 15% | 5–6 slides + demo video of 3–5 scenarios | `docs/demo_runbook.md`, `docs/scenario_matrix.md` exist | ❌ | Deck and demo video not produced. |

**Evidence a judge will look for:** a real video playing with boxes drawn, an event firing at the
right timestamp, a risk score with a *reason*, a human review action, and the assistant answering a
supervisor question from stored facts.

---

## 5. Current Repository Architecture

```
Upload (api/routes/videos.py)
  → ingest.py: ftyp magic bytes → ffprobe → codec/duration/size gates → SHA-256 → atomic move
  → POST /api/v1/runs (run_service.py) → creates RunModel + JobModel (atomic)
        ↓
worker/main.py  — single-worker DB lock (worker/lease.py, 60s lease / 10s heartbeat), 1s poll
  → worker/processor.py process_run()
        ├── Stage NORMALIZING → evidence/normalization.py (REAL: H.264, ≤1920, fps≤25, +faststart)
        ├── Stage DETECTING   → ***STUB — pipeline never invoked***
        ├── Stage VERIFYING   → ***no-op (vision/verify.py never called)***
        ├── Stage SCORING     → ***no-op (RiskEngine never called)***
        └── Stage WRITING_EVIDENCE → writes 1 empty track frame + events.json="[]"
        → atomic publish (REAL) → media_assets rows
        ↓
API (16 endpoints) → Next.js 15 app (dashboard / upload / run / event / camera setup)
```

**The library that is never called** (all real, all tested):
`vision/pipeline.py:67-291` `VisionPipeline.run()` → `interpolate_tracks` → `extract_track_kinematics`
→ per-package-track `HeroStateMachine` + `DraggingEngine` + `PlacementEngine` → `EmittedEvent`.

---

## 6. Current Implementation Analysis

### 6.1 Behaviour detectors that exist (5 event types, 3 engines)

| # | EventType | Engine | File:lines | Trigger |
|---|---|---|---|---|
| 1 | `DROP` | `HeroStateMachine` | `rules/drop_forceful_release.py:37-308` | vertical: `down_disp ≥ 0.50·h_ref` **and** `peak_down_speed ≥ 1.25 h/s` |
| 2 | `FORCEFUL_RELEASE` | same FSM | `:157-160, :245-246` | lateral: `horiz_disp ≥ 0.75·w_ref` **and** `peak_horiz_speed ≥ 1.50 h/s` |
| 3 | `DRAGGING` | `DraggingEngine` | `rules/dragging.py:28-251` | 800 ms window, person NEAR + ON_FLOOR + unsupported, `|Δcx| ≥ 1.00·w_ref`, `|Δcy| ≤ 0.25·h_ref`, ≥70% direction agreement |
| 4 | `PROHIBITED_ZONE` | `PlacementEngine` | `rules/placement.py:72-102` | package speed ≤0.25 h/s inside PROHIBITED polygon ≥1000 ms |
| 5 | `VISIBLE_SUPPORT_OVERHANG` | `PlacementEngine` | `:104-126` | bottom-15% footprint ∩ support polygon <0.80 for ≥500 ms |
| 6 | `STANDING_ON_PRODUCT` | **none** | enum only | Disabled in `config/behavior_rules.v1.yaml`; needs a pose model |

**Temporal reasoning is real:** `OBSERVING → CONTROLLED → RELEASED → RAPID_MOTION → IMPACT_CANDIDATE
→ EMIT`, with impact detection via deceleration (≥1.25 → ≤0.35 h/s within 300 ms) or floor contact,
settle detection, 2000 ms cooldown, and every transition recorded into a `DecisionTrace`. This maps
**exactly** onto the brief's worked example and is the strongest asset for the Innovation criterion.

**Risk scoring is real and blueprint-conformant** (`domain/risk.py:46-117`):
`score = clamp(base + motion + duration + support + zone, 0, 100)`; bases DROP 45 / FORCEFUL_RELEASE
55 / DRAGGING 40 / OVERHANG 35 / PROHIBITED_ZONE 50; tiers 0-39 LOW, 40-59 MEDIUM, 60-79 HIGH,
80-100 CRITICAL. Model confidence deliberately **does not** raise risk. Natural-language explanations
at `:119-175`.

### 6.2 Verified blockers

| Blocker | Evidence |
|---|---|
| Pipeline never invoked | `processor.py:84-93` — assigns `vision_pipe`, then never calls `.run()` |
| Events hardcoded empty | `processor.py:129` — `events_json_path.write_text("[]")` |
| No frame decoder | `vision/frames.py` has `FrameSampler` but nothing produces `Frame` objects from a file; no `VideoCapture` anywhere in `src/` |
| No adapter factory | `MODEL_BACKEND` (`config.py:53`) is referenced only by a health-check string compare (`api/routes/health.py:54`) |
| No model weights | `models/warehouse-v1.pt` absent; SHA in `checksums.json` = hash of empty string |
| `ultralytics` not installed | verified `ModuleNotFoundError` |
| COCO class-map bug | `ultralytics_adapter.py:86` — `self._class_map.get(cls_idx, "package")` maps **every** unknown class to `package` |
| Event clip/thumbnail never created | `EVENT_CLIP`/`THUMBNAIL` enum values are never written; `evidence/clips.py:36-151` is real but uncalled |
| Event video 404s | `events/[eventId]/page.tsx:146-150` falls back to `/api/v1/media/<run_id>`, which is never a media id |
| Explanation discarded | `api/routes/events.py:67` overwrites the rich risk explanation with `f"Detected {type} event…"`; `EventDetail` has no `decision_trace` field |
| `manifest_url` 404 | `runs.py:55,:95` return `/api/v1/media/{run_id}/manifest` — no such route |
| Assistant 0% | repo-wide grep: only 4 unused settings fields |
| `false_alert_rate` never computed | `services/analytics.py:66,130` hardcode `None` |
| No time dimension | no shift/date/bay/camera column anywhere → "today's unloading" is inexpressible |
| Fake status pill | `layout.tsx:63-66` — "API Connected" is static markup, never calls `getHealth()` |
| E2E test fails today | `tests/e2e.spec.ts:11` asserts "Responsible AI Policy"; layout renders "Policy Notice:" |

---

## 7. Requirement vs Code Gap Analysis

| Req | Relevant Code | Current | Status | Required Change |
|---|---|---|---|---|
| F1 ingest | `services/ingest.py` | Excellent, layered validation | ✅ | **None — do not touch** |
| F2 detect | `adapters/ultralytics_adapter.py` | Adapter written, never constructed, no weights | ❌ | P0-1, P0-2 |
| F3 activities | — | Implicit via rules | 🟡 | Narrative only |
| F4 track | `vision/tracking.py` + ByteTrack cfg | Interpolation tested; tracker never run | ❌ | P0-2 |
| F5 behaviours | 3 engines | Real, tested, never invoked | ❌ | P0-3 |
| F6 normal vs damaging | `rules/base.py` quality gate | Real | ✅ | Surface it |
| F7 sequences | `HeroStateMachine` | Real FSM | ✅ | **Preserve — headline asset** |
| F8 risk | `domain/risk.py` | Real, never called by worker | ❌ | P0-3 |
| F9 evidence | `evidence/clips.py` | Real, never called | ❌ | P0-4 |
| F10-F14 assistant | none | Config scaffolding only | ❌ | P2-1 |
| F15 highlight on video | none | No overlay anywhere | ❌ | P1-3 |
| F16 risk category | `Badge.tsx` `RiskBadge` | Good | ✅ | Preserve |
| F17 timeline | `components/runs/Timeline.tsx` | Very good, run page only | ✅ | Reuse on event page if time |
| F18-F19, F23 summaries/trends | `services/analytics.py` | No time bucketing at all | ❌ | P2-2 (optional) |
| F20-F22 recurring/training/locations | — | Absent | ❌ | Deck narrative only |
| F24 ≥10 behaviours | 5 engines + `docs/scenario_matrix.md` S01-S10 | Scenarios documented, not demonstrable | 🟡 | P0 makes them demonstrable; framing per §10 |

---

## 8. Marking Criteria vs Current Code

| Criterion | Current Potential | Blocking Fact |
|---|---:|---|
| Innovation | ~9/15 | Design is strong but invisible — nothing runs |
| Technical Execution | ~10/20 | Stubbed worker is the single biggest deduction |
| AI + Video Integration | ~3/20 | Zero real inference today |
| UX & Feedback | ~5/10 | Broken video element is the first thing a judge clicks |
| Damage Prevention & Impact | ~8/20 | No events → no impact numbers |
| Presentation | 0/15 | Not yet produced |
| **Total** | **~35/100** | — |

---

## 9. Architectural Gaps

**Current:** a well-built library plus a well-built service shell, joined by a stub.

**Required:** the same architecture, actually connected, plus (a) a grounded query layer for the
assistant and (b) evidence artifacts the UI can render.

**The gap is integration, not architecture.** Do **not** redesign anything. The correct fix is three
new small modules (decoder, factory, assistant) and one rewritten function (`process_run`'s middle).

---

## 10. Reusable Existing Components — DO NOT REWRITE

| Component | Why preserve |
|---|---|
| `services/ingest.py` | Layered validation, magic bytes, ffprobe, atomic move — production quality |
| `evidence/normalization.py`, `evidence/clips.py`, `evidence/manifest.py` | Real FFmpeg work, correct padding/SHA logic; clips just needs calling |
| `vision/pipeline.py`, `features.py`, `tracking.py`, all `rules/` | Tested behaviour core; the differentiator |
| `domain/risk.py` | Blueprint-exact, bound by `test_domain_risk.py` |
| `repositories/*`, `migrations/` | Dense constraints, append-only reviews, media path resolution |
| `api/errors.py` | Correct RFC7807 |
| `worker/lease.py`, publish/orphan logic in `processor.py:257-316` | Real atomic publish |
| `components/runs/Timeline.tsx`, `components/ui/*`, `hooks/useRunPolling.ts` | Best frontend artifacts |
| `evaluation.py` | Provides the metrics for the impact slide |

**Framing for ≥10 behaviours** — `IMPLEMENTATION_BLUEPRINT.md` §3.1 instructs:
> *"describe this as three behavior engines covering ten predefined scenarios, not as ten
> independently trained behaviors."*

Use that language in the deck. `docs/scenario_matrix.md` already locks S01–S10 with expected event,
control status and expected tier. This is defensible and honest.

---

## 11. Components That Need Modification

`worker/processor.py` (rewrite stages 2–5), `adapters/ultralytics_adapter.py` (class map),
`api/routes/events.py` (stop discarding the explanation), `api/schemas.py` (add fields),
`api/routes/runs.py` (manifest_url), `apps/web/app/events/[eventId]/page.tsx` (media + overlay),
`apps/web/app/layout.tsx` (status pill + nav), `backend/requirements.txt` + `pyproject.toml` (deps).

## 12. Components That Need to Be Created

`vision/decode.py` (cv2 → `Frame` iterator), `vision/factory.py` (MODEL_BACKEND → adapter),
`services/assistant.py` + `api/routes/assistant.py` (grounded Q&A),
`apps/web/components/events/BoxOverlay.tsx`, `apps/web/app/assistant/page.tsx`,
`scripts/seed_demo.py` (ingest the 7 real videos and run them).

---

## 13. Risks and Potential Breaking Changes

| Risk | Why it matters | Mitigation |
|---|---|---|
| **Stock COCO YOLO detects no cartons** | COCO has no "box"/"carton" class. If `package` tracks are empty, **every rule engine emits nothing** and the demo still shows zero events. This is the plan's #1 risk. | **Spike first (P0-0).** Run detection on 2 real videos and count per-class hits *before* building on it. If packages don't detect, fall back to the working `ReplayAdapter` with hand-authored fixtures for the demo. Do not skip this gate. |
| Class-map default sends everything to `package` | `ultralytics_adapter.py:86` would label cars/chairs as packages, producing absurd events | Replace with an explicit allowlist; drop unmapped classes |
| Rules are tuned in `h_ref`/`w_ref` units for a calibrated camera | Real footage has different scale/angle than the synthetic fixtures; thresholds may never trigger or may over-trigger | Accept prototype-quality; if zero events fire, relax thresholds via `config/behavior_rules.v1.yaml` **and disclose the tuning** in the deck |
| No camera calibration for the 7 real videos | `PlacementEngine` needs floor/zone/support polygons per camera; only `camera.demo.v1.json` exists | Demo placement rules on the calibrated demo camera; for real videos rely on DROP/FORCEFUL_RELEASE/DRAGGING which need no polygons |
| Changing `process_run` breaks `test_worker_execution.py` | That test injects a pipeline and asserts current stub behaviour | Keep the injected-`pipeline` parameter contract; run the suite after |
| Adding `EventDetail` fields breaks the frontend contract | `lib/schema.d.ts` is generated from `contracts/openapi.json` | Regenerate both: `python -m warehouse_ai.cli export-openapi contracts/openapi.json` then `pnpm --dir apps/web contract:generate` |
| Ultralytics is AGPL-3.0 | Licensing exposure | `THIRD_PARTY.md` already documents the AGPL gate — keep it accurate |
| Model SHA is the empty-string hash | Provenance claims in manifests become false | Recompute and update `models/checksums.json` for whatever weights are actually used |
| Time spent coding leaves no time to submit | Deck + demo video are 15% **and** the submission artifact | **Hard-reserve the final block** (§16) |

---

## 14. Target Architecture

```
data/video/*.mp4 (7 real warehouse videos)
   → POST /api/v1/videos (ingest.py, unchanged)
   → POST /api/v1/runs   (run_service.py, unchanged)
        ↓ worker claims job
   process_run():
     NORMALIZING  → normalization.py                                     [unchanged]
     DETECTING    → decode.py (cv2) → FrameSampler(10fps)
                    → factory.py → UltralyticsAdapter(yolo11n, COCO map) [NEW]
                    → VisionPipeline.run(frames)                         [existing, now called]
     SCORING      → RiskEngine.score() per event → score/tier/explanation [existing, now called]
     WRITING_EVIDENCE
                  → real tracks.jsonl.gz + real events.json
                  → clips.py per event → EVENT_CLIP + THUMBNAIL assets   [existing, now called]
                  → EventModel rows with facts_json + decision_trace_json
     PUBLISH      → atomic publish                                       [unchanged]
        ↓
   GET /api/v1/events/{id} → now returns real explanation + decision_trace + working clip_id
   GET /api/v1/assistant/query → services/assistant.py over the events table   [NEW]
        ↓
   Next.js: event page plays real clip with BoxOverlay; /assistant chat page   [NEW]
```

---

## 15. Detailed File-by-File Implementation Plan

### ── P0 — CRITICAL PATH (without these there is no demo) ──

#### P0-0. SPIKE / GO-NO-GO — detector reality check *(do this first, timebox 30 min)*
**Why:** the entire plan rests on stock COCO YOLO producing usable `person` and package-proxy tracks
on real warehouse footage. Verify before investing.

Steps:
1. `.\.venv\Scripts\python.exe -m pip install ultralytics` (pulls torch — expect a few minutes).
2. Ad-hoc script (scratchpad, not committed): load `yolo11n.pt` (auto-downloads), run
   `model.track(source=<one of data/video/*.mp4>, persist=True)` over ~200 frames, and print a
   histogram of detected COCO class names + counts.
3. Repeat for a second video (use `Throwing seating cartons…` and `Rolling and dropping carton`).

**Decision gate:**
- If `person` is reliable **and** some carton-like class fires (`suitcase`, `backpack`, `handbag`,
  `bed` for mattresses, `refrigerator`/`chair` for cupboards) → **proceed with P0-1.**
- If package-proxy detections are near zero → **switch to `ReplayAdapter`**: author
  `tracks.jsonl.gz` fixtures for 3 demo clips and skip P0-1/P0-2's detector half. The pipeline,
  rules, risk and evidence work identically; only perception is replaced. Say so honestly in the deck.

#### P0-1. `backend/requirements.txt`, `backend/pyproject.toml` — MODIFY
- **Why:** `ultralytics` is not installed; the detector cannot load.
- **Change:** add `ultralytics>=8.3.0` (and it will pull `torch`). Keep the AGPL note in
  `THIRD_PARTY.md` accurate.
- **Validation:** `python -c "import ultralytics"` succeeds.

#### P0-2. `backend/src/warehouse_ai/vision/decode.py` — **CREATE**
- **Why:** F1/F4. Nothing converts an MP4 into `Frame` objects; this is the missing first link.
- **New logic:** `decode_frames(path: Path) -> Iterator[Frame]` using `cv2.VideoCapture`, yielding
  `Frame(bgr=..., timestamp_ms=...)` where timestamp comes from `CAP_PROP_POS_MSEC` (fall back to
  `frame_index * 1000/fps` if it returns 0). Release the capture in a `finally`.
- **Reuse:** feed the output through the **existing** `FrameSampler(target_fps=settings.INFERENCE_FPS)`
  in `vision/frames.py:6-26` — do not write new sampling logic.
- **Dependencies:** check the exact `Frame` field names in `domain/models.py` first.
- **Validation:** new unit test decodes one real video and asserts monotonically increasing
  timestamps and ~10 fps spacing after sampling.

#### P0-3. `backend/src/warehouse_ai/vision/factory.py` — **CREATE**
- **Why:** `MODEL_BACKEND` is configured but nothing ever constructs an adapter.
- **New logic:** `build_detector_tracker(settings) -> DetectorTracker` returning `UltralyticsAdapter`
  when `MODEL_BACKEND == "ultralytics"` and `ReplayAdapter` when `"replay"`; raise a clear error
  otherwise. Read tracker config from `config/tracker.bytetrack.v1.yaml`.
- **Validation:** unit test asserts each branch returns the right type; replay branch needs no weights.

#### P0-4. `backend/src/warehouse_ai/vision/adapters/ultralytics_adapter.py` — MODIFY
- **Why:** `:86` maps every unrecognised COCO id to `"package"` — with stock weights that mislabels
  cars, chairs and people-adjacent objects as product.
- **Change:** make `_class_map` injectable; add a COCO preset
  (`0→person`; `24,26,28→package`; `59→package` for mattresses — tune from the P0-0 histogram) and
  **drop** any class not in the map instead of defaulting. Keep `_compute_model_hash`, the
  confidence gate, and the normalise/clamp logic **exactly as they are**.
- **Preserve:** the `DetectorTracker` protocol shape — `pipeline.py` depends on it.
- **Validation:** existing `test_pipeline.py` still passes; new test asserts unmapped classes drop.

#### P0-5. `backend/src/warehouse_ai/worker/processor.py` — **MODIFY (the core fix)**
- **Why:** this is *the* blocker. Stages 2–5 are no-ops and events are hardcoded empty.
- **Changes:**
  - Stage DETECTING: if no `pipeline` injected, build one —
    `VisionPipeline(detector_tracker=build_detector_tracker(settings), ...)` — then **actually call**
    `result = vision_pipe.run(frames)` with `frames = FrameSampler(settings.INFERENCE_FPS).sample(decode_frames(norm_output_path))`.
    **Delete `FallbackPipeline` entirely.**
  - Stage SCORING: for each `EmittedEvent`, call the existing `RiskEngine` to get score, tier and
    explanation; do not invent a new formula.
  - Stage WRITING_EVIDENCE: write the **real** track frames to `tracks.jsonl.gz` (keep
    `gzip.GzipFile(..., mtime=0)` + `sort_keys=True` — reproducibility is asserted by
    `test_tracking.py`), write real `events.json`, and build `EventModel` rows with
    `facts_json` + `decision_trace_json` populated.
  - Replace the `"0"*64` placeholder SHAs (`:216-220`) with the real rules/risk/camera hashes.
- **Preserve:** the `pipeline` injection parameter (tests depend on it), progress-update calls, the
  atomic publish block (`:257-298`) and orphan-on-failure (`:302-316`).
- **Validation:** `pytest backend/tests -v` (47 must still pass), then a real run must produce
  `event_count > 0`.

#### P0-6. `backend/src/warehouse_ai/worker/processor.py` — event clips **(same file, distinct task)**
- **Why:** F9/F15 and the visibly broken video on the event page.
- **Change:** after events are persisted, call the **existing** `evidence/clips.py` per event to
  produce the clip + thumbnail, and insert `EVENT_CLIP` / `THUMBNAIL` `MediaAssetModel` rows with
  `event_id` set. `api/routes/events.py:41-52` already reads these and will start returning non-null
  `clip_id`/`thumbnail_id` with no frontend change.
- **Validation:** `GET /api/v1/events/{id}` returns non-null `media.clip_id`; that media id streams 206.

### ── P1 — DEMO-VISIBLE CORRECTNESS ──

#### P1-1. `api/routes/events.py` + `api/schemas.py` — MODIFY
- **Why:** F11 ("explain **why**") is fully computed then thrown away. `events.py:67` replaces the
  rich explanation with `f"Detected {type} event…"`, and `EventDetail` has no `decision_trace` field.
- **Change:** return the stored explanation from `decision_trace_json`; add `decision_trace` to
  `EventDetail`. Then regenerate the contract **and** the TS types (see §13 risk row).
- **Validation:** event page shows a real factor breakdown, not a stub sentence.

#### P1-2. `api/routes/runs.py` — MODIFY
- **Why:** `:55` and `:95` return `manifest_url="/api/v1/media/{run_id}/manifest"` → guaranteed 404.
- **Change:** return the real `MANIFEST` media id, or drop the field. Prefer returning the media id.

#### P1-3. `apps/web/components/events/BoxOverlay.tsx` — **CREATE** + wire into `app/events/[eventId]/page.tsx`
- **Why:** "AI-detected objects" is an explicit deliverable in the demo slide and is **entirely
  missing** — no canvas or SVG overlay exists anywhere in the repo.
- **New logic:** absolutely-positioned SVG over the `<video>`; given normalized `bbox_xyxy_norm`
  tracks for the current `currentTime`, draw rects + `class #id` labels. Bboxes are already stored
  normalized, so scaling is `x * clientWidth`.
- **Note:** `evidence/overlay.py` already renders boxes server-side with PIL but is only used in
  tests. Client-side SVG is cheaper than producing a burned-in annotated video today.
- **Validation:** boxes visibly track the product through a drop in the demo clip.

#### P1-4. `apps/web/app/layout.tsx` — MODIFY *(small, do it — a judge may notice)*
- **Why:** `:63-66` renders a hardcoded "API Connected" pill that never checks anything. That is a
  false claim in a Responsible-AI-judged submission. `/runs` and `/events` also have no nav entry.
- **Change:** wire the pill to `api.getHealth()` (client island) or remove it. Optionally add nav.

### ── P2 — RUBRIC VALUE (only if P0+P1 land with time to spare) ──

#### P2-1. `services/assistant.py` + `api/routes/assistant.py` + `apps/web/app/assistant/page.tsx` — **CREATE**
- **Why:** F10-F14 — an entire Expected-Solution capability at 0%, feeding two 20% criteria.
- **Approach (per user's decision — no LLM):** intent-match a small set of supervisor questions
  against the events table and answer from stored facts:
  - "show high-risk events" → filter `risk_tier IN (HIGH, CRITICAL)`
  - "why was this high risk?" → return the stored risk explanation + factor breakdown
  - "most common risky behaviours" → group by `event_type`
  - "summarize this run/shift" → counts by tier + type + recommended actions
- **Grounding rule:** every answer must cite `event_id`s it used, and the endpoint must return
  "no matching events" rather than prose when the set is empty. This satisfies *"respond using the
  events detected by the computer-vision system rather than inventing information"* by construction.
- **Recommendations:** reuse the good-practice column from the assignment's Good/Bad Practice table
  (e.g. dragging → "Use a trolley or pallet truck instead of dragging products on the floor").
- **Disclaimer:** render "AI-generated summary; verify against evidence." per blueprint §20.4.

#### P2-2. `services/analytics.py` — MODIFY *(optional)*
- **Why:** F18/F19/F23 — no time bucketing exists, so "today's unloading" is inexpressible; also
  `false_alert_rate` is hardcoded `None` at `:66,:130` despite being in the response schema.
- **Change:** add optional date-range params and a by-day bucket; compute `false_alert_rate` from
  reviews (`REJECTED` / total reviewed).
- **Skip if short on time** — lower demo value than P0/P1.

#### P2-3. Extra detectors *(stretch only, per user's "both" decision)*
Highest value from the real videos: **rolling** (aspect-ratio oscillation), **stepping on product**
(person bbox bottom inside package bbox — no pose model needed), **heavy-on-light stacking**
(larger bbox vertically above smaller). Only attempt with genuine time left; the 3-engines/10-scenarios
framing already answers F24.

---

## 16. Implementation Order (time-boxed — hours only)

| # | Block | Est. | Rationale |
|---|---|---:|---|
| 0 | **P0-0 spike + go/no-go** | 0:30 | Everything downstream depends on the answer. Never build on an unverified detector. |
| 1 | P0-1 deps | 0:15 | Trivial, unblocks all |
| 2 | P0-2 decode + P0-3 factory + P0-4 class map | 0:40 | Bottom-up: data in before logic |
| 3 | **P0-5 wire `process_run`** | 1:15 | The single highest-value change in the repo |
| 4 | P0-6 event clips | 0:30 | Fixes the most visible bug (404 video) |
| 5 | **Checkpoint: seed + run 3 real videos** | 0:20 | *Stop and confirm real events appear before adding features* |
| 6 | P1-1, P1-2, P1-4 | 0:35 | Small, high-visibility correctness |
| 7 | P1-3 bbox overlay | 0:45 | The "AI-detected objects" demo shot |
| 8 | P2-1 assistant | 0:45 | Whole missing capability, two 20% criteria |
| 9 | Full test suite + `scripts/verify.ps1` | 0:20 | Regression gate |
| 10 | **RESERVED: demo video + 5-6 slide deck + submit** | **1:15** | **Non-negotiable — 15% of marks and the actual submission** |

**Why this order minimizes breakage:** dependencies flow upward (decode → adapter → pipeline →
persistence → API → UI), so each layer is verifiable before the next consumes it. The checkpoint at
step 5 is the project's true success/failure line — if real events do not appear there, stop adding
features and pivot to the replay fallback so there is *something* to demo.

---

## 17. Testing Strategy

### Unit
- `decode_frames` — monotonic timestamps, correct count, handles a real MP4.
- `build_detector_tracker` — returns correct type per `MODEL_BACKEND`; replay needs no weights.
- COCO class mapping — unmapped classes are dropped, not defaulted to `package`.
- Preserve all existing `test_domain_risk.py` / `test_rules.py` / `test_tracking.py` assertions.

### Integration
- `process_run` on a short real clip → `event_count > 0`, `tracks.jsonl.gz` has >1 frame,
  `events.json != "[]"`, `EVENT_CLIP` + `THUMBNAIL` rows exist.
- `test_worker_execution.py` must still pass with the injected-pipeline contract intact.
- `GET /api/v1/events/{id}` returns a real explanation and non-null `media.clip_id`.

### End-to-End
- Upload a real warehouse video → run → poll to `SUCCEEDED` → events appear on the run page →
  click event → clip plays with boxes → submit a human review → assistant answers about that run.

### Edge cases
- Video with **zero** detected events (control clip) → run still `SUCCEEDED`, empty state renders.
- Detector returns no `package` tracks → must not crash; must log clearly.
- Very short clip (< engine minimum durations) → no spurious events.
- Event at t=0 or at end of video → clip padding must clamp (`clips.py` pads ±1500 ms).

### Criterion → test mapping

| Criterion | Test | Expected |
|---|---|---|
| F2/F4 detection+tracking | integration on real clip | ≥1 tracked `person`; stable track ids |
| F5/F7 behaviour + sequence | `test_rules.py` + real run | ≥1 DROP/DRAGGING with a `DecisionTrace` |
| F8 risk | `test_domain_risk.py` | blueprint worked example exact |
| F9/F15 evidence | integration | clip + thumbnail stream 206 |
| F11 explanation | API test | explanation ≠ the stub string |
| F10-F14 assistant | API test | answer cites `event_id`s; empty set → "no matching events" |
| F24 ≥10 scenarios | `docs/scenario_matrix.md` + eval report | S01-S10 documented; ≥8/10 per blueprint gate |

---

## 18. Rubric Coverage Matrix

| Criterion | Now | Required Changes | Evidence After | Full marks? |
|---|---:|---|---|---|
| Innovation 15% | ~9 | P0-5 makes the FSM + DecisionTrace observable; P2-1 assistant | Live state-machine trace on a real drop | Likely 12-14 |
| Technical Execution 20% | ~10 | P0-1…P0-6; suite green | Real events from real video; 47+ tests pass | Likely 15-17 |
| AI + Video Integration 20% | ~3 | P0 entire path + P1-3 overlay | Boxes tracking product → event fires → risk scored | Likely 15-18 |
| UX & Feedback 10% | ~5 | P0-6 (fix 404), P1-3, P1-4 | Working clip playback + review workflow | Likely 7-8 |
| Damage Prevention 20% | ~8 | Surface `evaluation.py` metrics; prevention framing; P2-1 recommendations | Impact slide with P/R + false-alert rate | Likely 14-16 |
| Presentation 15% | 0 | Block 10 | 5-6 slides + 3-5 scenario demo video | Likely 12-14 |
| **Total** | **~35** | — | — | **~75-87** |

---

## 19. Final Implementation Checklist

```
SPIKE
[ ] ultralytics installed; stock yolo11n loads
[ ] Class histogram captured on >=2 real videos
[ ] GO/NO-GO recorded (COCO path vs replay fallback)

P0 - CRITICAL PATH
[ ] ultralytics added to requirements.txt + pyproject.toml
[ ] vision/decode.py created; feeds existing FrameSampler
[ ] vision/factory.py created; both backends constructible
[ ] ultralytics_adapter class map = explicit allowlist; unmapped dropped
[ ] FallbackPipeline DELETED; VisionPipeline.run() actually called
[ ] RiskEngine invoked; score/tier/explanation persisted
[ ] Real tracks.jsonl.gz (mtime=0, sort_keys) + real events.json written
[ ] EventModel rows have facts_json + decision_trace_json
[ ] Placeholder "0"*64 SHAs replaced with real hashes
[ ] EVENT_CLIP + THUMBNAIL assets created per event
[ ] CHECKPOINT: a real video produces event_count > 0

P1 - DEMO CORRECTNESS
[ ] events.py returns the real explanation (stub string removed)
[ ] decision_trace exposed on EventDetail
[ ] contracts/openapi.json regenerated AND schema.d.ts regenerated
[ ] manifest_url returns a real media id (or removed)
[ ] BoxOverlay renders boxes over the event clip
[ ] "API Connected" pill wired to getHealth() or removed

P2 - IF TIME
[ ] Assistant endpoint answers 4 intents, cites event_ids, empty-set safe
[ ] Assistant UI page + disclaimer rendered
[ ] Analytics false_alert_rate computed (no longer None)

GATES
[ ] pytest backend/tests -v  -> all pass
[ ] scripts/verify.ps1       -> all three gates pass
[ ] e2e.spec.ts:11 "Responsible AI Policy" assertion reconciled with layout copy
[ ] Demo rehearsed end to end at least once

SUBMISSION (do not skip)
[ ] Demo video recorded covering 3-5 scenarios
[ ] Deck: 5-6 slides (Solution/Team, Problem+Journey, Architecture+Stack, Screenshots+Demo, Impact+Validation)
[ ] Responsible-AI slide content drawn from blueprint §20.5 + docs/model_card.md
[ ] Submitted via the registration form
```

---

## 20. Final Recommendation

**Do P0 in order, stop at the checkpoint, and protect the final block.** The repository's problem is
not quality — much of this code is better than typical hackathon output — it is that a single stubbed
function makes all of it invisible. Fixing `process_run` converts roughly 60% of the existing
codebase from dead weight into demonstrable capability. That is by far the highest-leverage hour
available.

**Be honest in the deck about the detector.** Stock COCO weights used as a package proxy is a
legitimate prototype choice; claiming a trained 4-class warehouse model that does not exist is not,
and `docs/model_card.md` would contradict it. Frame it as "perception is swappable behind a
`DetectorTracker` protocol; the behaviour intelligence is the contribution."

### Answers to the required questions

1. **What percentage of the assignment is already implemented?**
   ~45% by code volume, but **~15% by demonstrable capability**. Ingestion, persistence, API, job
   system, rules library, risk engine and evidence modules are real; the integration that makes them
   observable is not, so almost nothing is currently *shown*.

2. **What percentage of the marking criteria is currently satisfied?**
   ~35/100. Biggest holes: AI+Video Integration (~3/20) and Presentation (0/15).

3. **The 5 highest-priority changes**
   1. Wire `process_run` to actually call `VisionPipeline.run()` (P0-5) — the single blocker.
   2. Frame decoder + adapter factory + COCO class map (P0-2/3/4) — feeds #1.
   3. Generate `EVENT_CLIP`/`THUMBNAIL` (P0-6) — fixes the 404 video a judge clicks first.
   4. Stop discarding the risk explanation (P1-1) — F11 is computed then thrown away.
   5. Reserve time for deck + demo video — 15% and the submission itself.

4. **Which existing code should be preserved?**
   `services/ingest.py`, all of `evidence/`, `vision/pipeline.py` + `features.py` + `tracking.py` +
   all `rules/`, `domain/risk.py`, `repositories/*` + migrations, `api/errors.py`, `worker/lease.py`
   and the atomic publish/orphan logic, `Timeline.tsx`, `components/ui/*`, `useRunPolling.ts`,
   `evaluation.py`. Do not refactor any of it.

5. **Which existing code is incorrect and must be changed?**
   `processor.py:84-93` (pipeline never invoked) and `:129` (hardcoded `[]`) and `:216-220`
   (placeholder SHAs); `ultralytics_adapter.py:86` (unknown→`package`); `events.py:67` (explanation
   overwritten); `runs.py:55,:95` (`manifest_url` 404); `analytics.py:66,130` (`false_alert_rate`
   always `None`); `layout.tsx:63-66` (fake status pill); `e2e.spec.ts:11` (asserts copy that does
   not exist → currently failing).

6. **Which new files are actually necessary?**
   Only five: `vision/decode.py`, `vision/factory.py`, `services/assistant.py`,
   `api/routes/assistant.py`, `apps/web/components/events/BoxOverlay.tsx`
   (+ `apps/web/app/assistant/page.tsx` and a `scripts/seed_demo.py` convenience). Everything else is
   modification.

7. **What is the safest implementation order?**
   §16. Bottom-up along the data dependency (decode → adapter → pipeline → persistence → API → UI),
   with a hard go/no-go spike first and a checkpoint after P0-6 before any feature work.

8. **What tests must pass before considering it complete?**
   `pytest backend/tests -v` (47 existing + new decode/factory/class-map tests), `scripts/verify.ps1`
   all three gates (tests + `tsc --noEmit` + `next build`), the integration assertion that a real
   video yields `event_count > 0` with a streaming clip, and one rehearsed manual end-to-end run.

9. **What evidence demonstrates full marks?**
   A real warehouse video playing with live bounding boxes; an event firing at the correct timestamp
   with a state-machine decision trace; a risk score with its factor breakdown ("Base 55 + motion 9 +
   critical-zone 20 = 84"); a human reviewer setting a verdict; the assistant answering "why was this
   high risk?" citing that event id; and an impact slide quoting precision/recall/false-alert-rate
   from `evaluation.py` with numerator/denominator counts, described as prototype results.

---

## Verification (end to end)

```powershell
# 1. deps
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 2. backend gates
.\.venv\Scripts\python.exe -m pytest backend\tests -v

# 3. contract regeneration after any schema change
.\.venv\Scripts\python.exe -m warehouse_ai.cli export-openapi contracts\openapi.json
pnpm --dir apps\web contract:generate

# 4. full gate (tests + typecheck + production build)
.\scripts\verify.ps1        # NOTE: do NOT wrap in 2>&1 - PS 5.1 misreports pnpm stderr as fatal

# 5. run the app and drive it manually
.\scripts\dev.ps1
#    upload a file from data\video\  -> run -> event -> clip plays with boxes -> review -> assistant
```

**Known environment notes:** restart the dev server after editing `app/layout.tsx` or `globals.css`
(hot reload corrupts the webpack cache — symptom is `__webpack_modules__[moduleId] is not a function`;
fix is stop server, `rm -rf apps/web/.next`, restart). `models/warehouse-v1.pt` does not exist —
whatever weights you use, update `models/checksums.json` so provenance claims stay true.
