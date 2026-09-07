"""CLI commands for warehouse_ai including OpenAPI export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from warehouse_ai.api.app import create_app
from warehouse_ai.config import REPO_ROOT


def export_openapi(output_path: str) -> None:
    """Generate and write committed OpenAPI JSON contract."""
    app = create_app()
    openapi_schema = app.openapi()

    target = Path(output_path)
    if not target.is_absolute():
        target = (REPO_ROOT / target).resolve()

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
        f.write("\n")

    print(f"Exported OpenAPI schema to {target}")


def seed_demo_camera() -> None:
    """Seed demo camera profile from config/camera.demo.v1.json if not present."""
    from warehouse_ai.repositories.camera_profiles import (
        create_camera_profile_version,
        get_camera_profile,
    )
    from warehouse_ai.repositories.database import get_session_factory

    config_file = REPO_ROOT / "config" / "camera.demo.v1.json"
    if not config_file.exists():
        print(f"Config file not found: {config_file}")
        return

    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    factory = get_session_factory()
    with factory() as session:
        existing = get_camera_profile(session, data["id"], 1)
        if not existing:
            create_camera_profile_version(
                session=session,
                profile_id=data["id"],
                name=data["name"],
                profile_json=json.dumps(data, sort_keys=True),
                sha256=data["profile_sha256"],
                created_at=data["created_at"],
            )
            session.commit()
            print(f"Seeded demo camera profile '{data['id']}' v1")
        else:
            print(f"Camera profile '{data['id']}' v1 already exists.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Warehouse AI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export-openapi", help="Export OpenAPI schema JSON")
    export_parser.add_argument("output", help="Path to output openapi.json file")

    subparsers.add_parser("seed-camera", help="Seed default demo camera profile")

    args = parser.parse_args()

    if args.command == "export-openapi":
        export_openapi(args.output)
    elif args.command == "seed-camera":
        seed_demo_camera()


if __name__ == "__main__":
    main()
