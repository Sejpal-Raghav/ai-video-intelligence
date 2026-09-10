"""P0-0 Spike: Print COCO class histogram on real warehouse videos.

Run from repo root:
  .\.venv\Scripts\python.exe scripts\detect_spike.py
"""

import sys
from collections import Counter
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

DATA_DIR = Path(__file__).parent.parent / "data" / "video"
TEST_VIDEOS = [
    DATA_DIR / "Rolling and dropping carton.mp4",
    DATA_DIR / "Throwing seating cartons, using strap to hold.mp4",
    DATA_DIR / "Dock level, dragging cupboard.mp4",
]
MAX_FRAMES_PER_VIDEO = 200

def run_spike():
    from ultralytics import YOLO  # type: ignore

    model = YOLO("yolo11n.pt")  # auto-downloads ~6MB
    print(f"\nLoaded model: yolo11n.pt\n{'='*60}")

    overall: Counter = Counter()

    for video_path in TEST_VIDEOS:
        if not video_path.exists():
            print(f"  [SKIP] not found: {video_path.name}")
            continue

        print(f"\nProcessing: {video_path.name}")
        class_counts: Counter = Counter()
        frame_count = 0

        results = model.track(
            source=str(video_path),
            persist=True,
            stream=True,
            verbose=False,
            device="cpu",
        )

        for result in results:
            if frame_count >= MAX_FRAMES_PER_VIDEO:
                break
            frame_count += 1
            if result.boxes is not None:
                for cls_idx in result.boxes.cls.tolist():
                    class_name = model.names[int(cls_idx)]
                    class_counts[class_name] += 1

        print(f"  Frames analysed: {frame_count}")
        for cls, count in sorted(class_counts.items(), key=lambda x: -x[1]):
            coco_id = {v: k for k, v in model.names.items()}.get(cls, "?")
            print(f"    COCO id {coco_id:3d}  {cls:<20s}  {count:5d} detections")
        overall.update(class_counts)

    print(f"\n{'='*60}")
    print("OVERALL across all test videos:")
    for cls, count in sorted(overall.items(), key=lambda x: -x[1]):
        print(f"  {cls:<25s} {count:6d}")

    print(f"\n{'='*60}")
    print("GO/NO-GO ASSESSMENT:")
    person_ok = overall.get("person", 0) >= 10
    pkg_proxies = sum(overall.get(c, 0) for c in ["backpack", "handbag", "suitcase", "bed", "potted plant", "refrigerator", "clock", "book"])
    pkg_ok = pkg_proxies >= 5

    print(f"  person detections:         {overall.get('person', 0):5d}  {'✅ OK' if person_ok else '❌ WEAK'}")
    print(f"  package-proxy detections:  {pkg_proxies:5d}  {'✅ GO' if pkg_ok else '❌ NO-GO — switch to ReplayAdapter'}")

    if person_ok and pkg_ok:
        print("\n  DECISION: GO → proceed with UltralyticsAdapter path")
    else:
        print("\n  DECISION: NO-GO → use ReplayAdapter with hand-authored fixtures")

if __name__ == "__main__":
    run_spike()
