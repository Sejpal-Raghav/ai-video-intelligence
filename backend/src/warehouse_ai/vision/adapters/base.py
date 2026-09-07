from typing import Iterable, Protocol, Sequence

from warehouse_ai.domain.models import Frame, PersonPose, TrackedDetection


class DetectorTracker(Protocol):
    """Protocol for detector-tracker models (Section 5.3)."""
    backend_name: str
    model_sha256: str

    def process(self, frames: Iterable[Frame]) -> Iterable[Sequence[TrackedDetection]]:
        """Yield exactly one detection sequence for every input frame, in order."""
        ...


class PoseEstimator(Protocol):
    """Protocol for person pose estimation (Section 10.6)."""
    model_sha256: str

    def infer(self, frames: Iterable[Frame]) -> Iterable[Sequence[PersonPose]]:
        """Yield exactly one pose sequence for every input frame, in order."""
        ...
