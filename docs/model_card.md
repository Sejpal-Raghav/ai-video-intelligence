# Model Card: Warehouse Package Detector & Behavior Inference

**Model Name:** `warehouse-v1`  
**Architecture:** Ultralytics YOLO26n Custom Detector + ByteTrack  
**Date:** 2026-09-04  
**Maintainer:** Member 1 (Vision/ML)  

---

## 1. Intended Use

- **Primary Domain:** Fixed-camera warehouse package handling video analysis.
- **Intended Tasks:** Detect workers, packages, pallets, and material-handling equipment; track items across frames; estimate handling risk evidence.
- **Out-of-Scope Uses:**
  - Facial recognition or worker identity matching.
  - Emotion or intent inference.
  - Automated worker scoring or disciplinary actions.
  - Measurement of physical impact force, mass, or monetary damage without calibrated physical sensors.

---

## 2. Model Pipeline & Architecture

- **Detector:** YOLO26n initialized from seed weights and fine-tuned on warehouse packages with input size 960x960.
- **Tracker:** ByteTrack (class-aware, fixed camera, ReID disabled).
- **Temporal Verification:** Candidate-to-verifier cascade (10 FPS candidate pass with optional 25 FPS verifier reprocessing).
- **Rule Engine:** Deterministic state machine and predicate logic; risk explanation derived from measured kinematic factors.

---

## 3. Data & Splits

- **Training:** Take A partitions (independent staging takes).
- **Threshold Calibration:** Take B partitions.
- **Holdout Validation:** Take C locked partitions (zero leakage from training/development).

---

## 4. Limitations & Edge Cases

- Highly occluded packages (<25% visibility) cannot be reliably tracked.
- Extreme camera motion or pan/tilt/zoom causes tracker association failure and is explicitly rejected (`422 UNSUPPORTED_CAMERA_MODE`).
- Rapid lighting changes or reflections on polished warehouse floors can impact low-confidence boundaries.
