# Annotation Guide: Warehouse Handling Video Intelligence

**Owner:** Member 1 (Vision/ML)  
**Status:** Authoritative standard for spatial and temporal annotations  
**Reference:** IMPLEMENTATION_BLUEPRINT.md Sections 5.4, 12.2, and 17.1  

---

## 1. Object Detection Classes

Annotate visible instances across the following 4 classes only:

| Class ID | Description | Rules & Boundaries |
|---|---|---|
| `person` | Warehouse worker or handler | Tight bounding box around body, including footwear and limbs. |
| `package` | Handled box, carton, or parcel | Tight box around outer edges. Primary target for tracking. |
| `pallet` | Wooden, plastic, or metal pallet | Bounding box enclosing the pallet structure. |
| `equipment` | Material handling equipment | Trolleys, hand trucks, forklifts, pallet jacks. |

### Visibility & Occlusion
- Mark an object as **difficult / ignored** if less than 25% of the object is visible.
- Never generate boxes from raw model predictions without human verification and correction.

---

## 2. Frame Sampling Protocol

- **Uniform rate:** Sample frames at 2 FPS across the entire clip.
- **Decisive boundaries:** Sample every frame at critical event transition boundaries:
  - Moment of package release or loss of hand contact.
  - Peak velocity / rapid trajectory point.
  - Impact / contact with floor or surface.
  - Settle frame (package motion cessation).

---

## 3. Temporal Event Ground Truth

Temporal events are documented in `data/annotations/events.v1.json` with the schema:

```json
{
  "schema_version": "event-annotations.v1",
  "clips": [
    {
      "video_sha256": "<hex>",
      "scenario_id": "S04_LATERAL_THROW",
      "expected_events": [
        {
          "event_type": "FORCEFUL_RELEASE",
          "start_ms": 4500,
          "end_ms": 6500
        }
      ],
      "annotator": "member-3",
      "adjudicator": "member-1"
    }
  ]
}
```

### Event Definitions
- **`DROP`**: Release followed by downward displacement (>= 0.50 package heights) and impact/settle.
- **`FORCEFUL_RELEASE`**: Release followed by lateral throw motion (>= 0.75 package widths) exceeding vertical displacement.
- **`DRAGGING`**: Package sliding on floor while associated with person and not on equipment (duration >= 800 ms).
- **`VISIBLE_SUPPORT_OVERHANG`**: Stationary package with > 20% footprint outside calibrated support surface for >= 500 ms.
- **`PROHIBITED_ZONE`**: Stationary package bottom-center inside prohibited polygon for >= 1000 ms.
- **Controls (`S01`, `S05`, `S08`)**: Expected events list MUST be empty `[]`.
