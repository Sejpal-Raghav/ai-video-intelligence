# Third-Party Dependencies and Licensing Register

## Licensing Decision

Per Section 5.2 of `IMPLEMENTATION_BLUEPRINT.md`:

- **Licensing Gate Decision**: `AGPL_OPEN_SOURCE`
- **Scope & Rationale**: The complete corresponding source code and required model/config artifacts will be published under compatible open-source terms (AGPL-3.0 compatible).
- **Ultralytics YOLO**: Complies with the AGPL-3.0 open-source requirement.

## Checksums and Versioning

### Model Weights
- **Model Checkpoint**: `yolo26n.pt` / `warehouse-v1.pt`
- **Tracked Checksums**: Recorded in `models/checksums.json`.

### Tool Binaries
- **FFmpeg**: System FFmpeg executable, resolved to absolute path at startup.
- **ffprobe**: System ffprobe executable, resolved to absolute path at startup.
