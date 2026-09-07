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


def main() -> None:
    parser = argparse.ArgumentParser(description="Warehouse AI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export-openapi", help="Export OpenAPI schema JSON")
    export_parser.add_argument("output", help="Path to output openapi.json file")

    args = parser.parse_args()

    if args.command == "export-openapi":
        export_openapi(args.output)


if __name__ == "__main__":
    main()
