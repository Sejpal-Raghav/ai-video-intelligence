# Data Management & Storage

This directory manages the dataset definitions, annotations, and splits for the Warehouse Handling Video Intelligence prototype.

## Partitioning Rules (Blueprint Section 5.4 & 12.2)

1. **Take A (Training)**: Model fine-tuning data if necessary.
2. **Take B (Development)**: Threshold calibration and development tuning.
3. **Take C (Holdout/Validation)**: Locked validation set. No training frame may appear in Take C.

Splitting occurs by original recording before frames are extracted.

## Directory Structure

```text
data/
├── annotations/      # Annotation JSON files (events.v1.json, bounding boxes)
├── golden/           # Small test fixtures and replay tracks for verification
├── splits.v1.json    # Locked scenario partitions
└── README.md
```
