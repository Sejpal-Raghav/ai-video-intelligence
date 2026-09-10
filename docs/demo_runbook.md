# Warehouse Video Intelligence: Demo Runbook

This runbook provides the step-by-step procedure for operating and demonstrating the complete end-to-end Warehouse Video Intelligence system in accordance with **Blueprint Section 18.2 & 18.3**.

---

## 1. System Requirements & Environment

- **Operating System:** Windows 11 / Linux / macOS
- **Runtime Dependencies:**
  - Python `3.11.9` with `warehouse-ai` installed (`pip install -e backend`)
  - Node.js `22.21.0` and `pnpm 12.x`
  - `ffmpeg` in system `PATH`
  - SQLite 3 (with WAL mode support)

---

## 2. Quickstart Startup (Single Command)

To start all three services simultaneously (FastAPI API server, background processing worker, and Next.js frontend), execute the automated startup script:

```powershell
# In PowerShell (Workspace Root):
.\scripts\dev.ps1
```

Or start the services individually in separate terminals:

### Terminal 1: Backend API Server
```powershell
uvicorn warehouse_ai.api.app:app --host 127.0.0.1 --port 8000 --reload
```
Verify readiness at `http://127.0.0.1:8000/readyz`.

### Terminal 2: Processing Worker
```powershell
python -m warehouse_ai.worker.main
```
The worker will register mutual exclusion locks in `worker_locks` and poll for `QUEUED` jobs every 1 second.

### Terminal 3: Web Application
```powershell
pnpm --dir apps/web dev
```
Open `http://localhost:3000` in your web browser.

---

## 3. Demonstration Workflow

### Step 1: Verify Camera Calibration
1. Navigate to `http://localhost:3000/settings/camera`.
2. Inspect the pre-calibrated `demo-camera` profile (or create a new profile with floor boundary, loading zone, and prohibited zone).
3. Confirm that all support polygons have the mandatory operator confirmation checked.
4. Click **Save Profile Version** to record an immutable version in SQLite.

### Step 2: Upload Warehouse Footage
1. Navigate to `http://localhost:3000/upload`.
2. Review the ingest constraints checklist (MP4 H.264, max 500 MB, max 600s, max 4K).
3. Drag and drop or browse for an MP4 surveillance video.
4. Select the calibrated camera profile (`demo-camera v1`).
5. Choose analysis mode (`LIVE` for multi-engine inference, or `REPLAY` for deterministic artifact replay).
6. **Check the mandatory Source Consent checkbox** confirming video capture compliance.
7. Click **Upload & Analyze Video**.

### Step 3: Real-Time Run Monitoring
1. The browser automatically navigates to `http://localhost:3000/runs/[runId]`.
2. Observe the real-time processing banner updating through stages:
   - `NORMALIZING` (H.264 / 25 FPS normalization)
   - `DETECTING` (YOLO26n + ByteTrack inference)
   - `VERIFYING` (Cascade candidate verification)
   - `SCORING` (Deterministic risk engine calculation)
   - `WRITING_EVIDENCE` (Evidence clips & thumbnails)
   - `COMPLETE` (100% atomic publication)
3. Note that the client polls every 1s, backing off to 5s after 2 minutes.

### Step 4: Interactive Video & Event Scrubber
1. Once processing finishes, the normalized video streams with HTML5 byte-range seeking (`206 Partial Content`).
2. Use the **Interactive Event Timeline** scrubber to jump directly to flagged event time intervals.
3. Filter events using risk chips (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) or review status.

### Step 5: Evidence Inspection & Human Review
1. Click **Details** on any detected event to navigate to `http://localhost:3000/events/[eventId]`.
2. Watch the isolated evidence clip and inspect the keyframe impact thumbnail.
3. Expand **Deterministic Kinematic & Spatial Facts** to view drop height, velocities, and displacement.
4. Expand **Proof-Carrying Decision Trace** to review predicate evaluations.
5. In the **Human Review Record** card, select a non-punitive verdict:
   - *Human-confirmed risk*
   - *Rejected*
   - *Uncertain*
6. Enter reviewer name and operational notes, then click **Append Review Revision**.
7. Observe that the revision counter increments to `#1`, permanently preserving audit history without overwriting.

### Step 6: Verify Cryptographic Manifest
1. Return to the run detail view and click the **Manifest** button.
2. Inspect `manifest.json` (`schema_version: run-manifest.v1`), verifying SHA-256 digests for model weights, rule configs, camera profile, input video, and output evidence artifacts.

---

## 4. Guaranteed-Working Demo Path (Replay Mode)

The default `MODEL_BACKEND=ultralytics` path uses a stock COCO-pretrained
detector as a package-class proxy (see `docs/model_card.md` Section 0 for
why `warehouse-v1.pt` doesn't exist yet). That detector was validated
against all 7 videos in `data/video/`; only some produce a qualifying event,
and which ones can vary run to run since detection is not deterministic.

If you need a **guaranteed, deterministic** demonstration of the full
pipeline (detection → tracking → temporal reasoning → risk scoring →
evidence clip → review workflow) — for example, right before a live demo —
use the checked-in replay fixture instead:

1. Set two environment variables before starting the worker (`scripts/dev.ps1`
   reads `.env`; for a one-off demo run, set them in the same shell before
   launching, or add them to `.env` temporarily and revert afterward):
   ```powershell
   $env:MODEL_BACKEND = "replay"
   $env:REPLAY_TRACKS_PATH = "data\replay\throwing-mattresses.tracks.jsonl.gz"
   ```
2. Upload `data/replay/throwing-mattresses-demo-clip.mp4` through the normal
   upload flow (Step 2 above).
3. The run will deterministically produce **one `DROP` event, risk tier
   `HIGH`, score 70**, with a real evidence clip and thumbnail cut from that
   video — exactly as verified by
   `backend/tests/integration/test_replay_fixture.py`.
4. **Revert `MODEL_BACKEND` to `ultralytics`** (or unset it) afterward — this
   fixture's track data is only valid for that specific clip; leaving
   `MODEL_BACKEND=replay` set would silently apply the same canned tracks to
   any other video you upload.

See `data/replay/README.md` for exactly why the demo clip is trimmed to 2.5
seconds and how the fixture was constructed.

---

## 5. Running Offline Evaluation Benchmark

To verify detection precision, recall, and false-alert rates against ground truth:

```powershell
pytest backend/tests/unit/test_evaluation.py -v
```
All metrics will be calculated greedily by highest temporal IoU ($\ge 0.30$) with controls evaluated for zero false alarms.
