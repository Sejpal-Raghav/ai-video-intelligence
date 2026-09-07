from enum import Enum


class EventType(str, Enum):
    DROP = "DROP"
    FORCEFUL_RELEASE = "FORCEFUL_RELEASE"
    DRAGGING = "DRAGGING"
    VISIBLE_SUPPORT_OVERHANG = "VISIBLE_SUPPORT_OVERHANG"
    PROHIBITED_ZONE = "PROHIBITED_ZONE"
    STANDING_ON_PRODUCT = "STANDING_ON_PRODUCT"


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class VerificationStatus(str, Enum):
    NOT_RUN = "NOT_RUN"
    PASSED = "PASSED"
    FAILED = "FAILED"


class ReviewVerdict(str, Enum):
    CONFIRMED_RISK = "CONFIRMED_RISK"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


class JobState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class JobStage(str, Enum):
    QUEUED = "QUEUED"
    NORMALIZING = "NORMALIZING"
    DETECTING = "DETECTING"
    VERIFYING = "VERIFYING"
    SCORING = "SCORING"
    WRITING_EVIDENCE = "WRITING_EVIDENCE"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class RunMode(str, Enum):
    LIVE = "LIVE"
    REPLAY = "REPLAY"


class MediaKind(str, Enum):
    SOURCE = "SOURCE"
    NORMALIZED = "NORMALIZED"
    ANNOTATED = "ANNOTATED"
    TRACKS = "TRACKS"
    EVENTS_JSON = "EVENTS_JSON"
    MANIFEST = "MANIFEST"
    EVENT_CLIP = "EVENT_CLIP"
    THUMBNAIL = "THUMBNAIL"
    TRACE = "TRACE"


class CameraMotion(str, Enum):
    FIXED = "FIXED"


class ZoneKind(str, Enum):
    ALLOWED = "ALLOWED"
    PROHIBITED = "PROHIBITED"


class ZoneSeverity(str, Enum):
    NORMAL = "NORMAL"
    SENSITIVE = "SENSITIVE"
    CRITICAL = "CRITICAL"


class ObjectClass(str, Enum):
    PERSON = "person"
    PACKAGE = "package"
    PALLET = "pallet"
    EQUIPMENT = "equipment"
