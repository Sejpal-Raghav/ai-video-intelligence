# Warehouse Scenario Matrix (S01 – S10)

This matrix maps all ten benchmark warehouse handling scenarios defined in **Blueprint Section 3 & 17**, detailing physical behavior classifications, control status, kinematic thresholds, and expected risk scoring.

---

## Scenario Overview

| Scenario ID | Title | Behavior Rule | Category | Expected Outcome | Risk Tier | Tolerance Window |
|---|---|---|---|---|---|---|
| **S01** | Benign Controlled Placement | None (Placement) | Control | **Control Pass** (No event) | N/A | Full duration |
| **S02** | Low Drop Freefall | `DROP` | Positive | `DROP` detected | **MEDIUM** | 1.5s – 2.6s (±250ms) |
| **S03** | High Drop Freefall | `DROP` | Positive | `DROP` detected | **HIGH** / **CRITICAL** | 2.0s – 3.4s (±250ms) |
| **S04** | Lateral Package Throw | `FORCEFUL_RELEASE` | Positive | `FORCEFUL_RELEASE` detected | **HIGH** | 4.5s – 6.5s (±250ms) |
| **S05** | Supported Hand Carry | None (Carry) | Control | **Control Pass** (No event) | N/A | Full duration |
| **S06** | Short Package Dragging | `DRAGGING` | Positive | `DRAGGING` detected | **MEDIUM** | 1.8s – 3.2s (±250ms) |
| **S07** | Prolonged Package Dragging | `DRAGGING` | Positive | `DRAGGING` detected | **HIGH** | 1.2s – 4.5s (±250ms) |
| **S08** | Compliant Pallet Placement | None (Placement) | Control | **Control Pass** (No event) | N/A | Full duration |
| **S09** | Pallet Edge Overhang | `VISIBLE_SUPPORT_OVERHANG` | Positive | `VISIBLE_SUPPORT_OVERHANG` | **HIGH** | 2.5s – 4.8s (±250ms) |
| **S10** | Prohibited Zone Staging | `PROHIBITED_ZONE` | Positive | `PROHIBITED_ZONE` detected | **CRITICAL** | 2.0s – 4.2s (±250ms) |

---

## Detailed Scenario Specifications

### S01: Benign Controlled Placement (Control)
- **Description:** Worker picks up package, places it onto an authorized conveyor surface with constant hand support until rest.
- **Predicates:** Contact sustained until vertical velocity reaches zero. Dwell duration exceeds 0.5s.
- **Control Expectation:** Must trigger **zero** risk alerts. Any alert is scored as a False Positive ($FP$).

### S02: Low Drop Freefall
- **Description:** Package released from approximately 0.5m above the floor with visible freefall acceleration.
- **Predicates:** Downward acceleration $\ge 0.8g$, freefall duration $\ge 150\text{ ms}$, impact deceleration spike.
- **Risk Score:** 45–65 (`MEDIUM`).

### S03: High Drop Freefall
- **Description:** Package slips or is dropped from shoulder/waist height ($\ge 1.2\text{m}$) directly onto concrete floor.
- **Predicates:** Downward acceleration $\ge 0.8g$, freefall duration $\ge 300\text{ ms}$, high impact kinetic energy estimate.
- **Risk Score:** 75–95 (`HIGH` or `CRITICAL`).

### S04: Lateral Package Throw (Hero Behavior)
- **Description:** Package forcefully tossed or laterally slid with horizontal trajectory across workspace.
- **Predicates:** Horizontal displacement $\ge 1.2\times$ package width; peak horizontal velocity $\ge 2.0\text{ heights/sec}$.
- **Risk Score:** 70–85 (`HIGH`).

### S05: Supported Hand Carry (Control)
- **Description:** Worker carries package securely across camera field of view with two-handed grip.
- **Predicates:** Track association confirms continuous worker overlap; vertical position stable.
- **Control Expectation:** Must trigger **zero** risk alerts.

### S06: Short Package Dragging
- **Description:** Heavy carton pulled along floor for a short distance ($1.0\text{m}$ to $1.5\text{m}$) without lifting.
- **Predicates:** Floor contact verified; continuous planar velocity $> 0.3\text{ m/s}$; contact duration $1.0\text{s}$ to $2.0\text{s}$.
- **Risk Score:** 40–60 (`MEDIUM`).

### S07: Prolonged Package Dragging
- **Description:** Carton dragged over long distance ($> 3\text{m}$) across warehouse floor.
- **Predicates:** Continuous dragging displacement exceeding $3.0\times$ package diagonal length; sustained friction duration $> 3.0\text{s}$.
- **Risk Score:** 70–85 (`HIGH`).

### S08: Compliant Pallet Placement (Control)
- **Description:** Package placed neatly within the boundary of a wooden pallet top surface without overhang.
- **Predicates:** Bounding box centroid strictly within calibrated `support_regions` polygon.
- **Control Expectation:** Must trigger **zero** risk alerts.

### S09: Pallet Edge Overhang
- **Description:** Package placed with $> 30\%$ of its base projecting beyond the visible perimeter of pallet.
- **Predicates:** Intersection of package footprint with convex `support_regions` polygon reveals base support ratio $< 0.70$.
- **Risk Score:** 65–80 (`HIGH`).

### S10: Prohibited Zone Staging
- **Description:** Staging package inside red-line pedestrian walkway or fire exit access lane.
- **Predicates:** Footprint centroid resides within `zones` polygon where `kind == "PROHIBITED"` and `severity == "CRITICAL"`.
- **Risk Score:** 90–100 (`CRITICAL`).

---

## Operational Vocabulary Notice

In compliance with **Blueprint Section 16.2**, all algorithmic detections and review actions use strictly non-punitive terminology:
- Use *"Human-confirmed risk"*, *"Rejected"*, *"Uncertain"*.
- Never use *"AI guilty"*, *"unsafe worker"*, or accusatory labels.
- Disclaimer displayed on all surfaces: *"Risk event, not confirmed damage."*
