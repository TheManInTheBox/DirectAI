#!/usr/bin/env python3
"""
Export the OpenAPI specification from the DirectAI API server.

Usage:
    python scripts/export-openapi.py              # writes docs/openapi.json
    python scripts/export-openapi.py -o out.json  # writes to custom path
    python scripts/export-openapi.py --yaml        # writes docs/openapi.yaml

Requires the api-server package to be installed:
    cd src/api-server && pip install -e .
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DirectAI OpenAPI spec")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: docs/openapi.json or docs/openapi.yaml)",
    )
    parser.add_argument(
        "--yaml",
        action="store_true",
        help="Export as YAML instead of JSON",
    )
    args = parser.parse_args()

    # Import the FastAPI app — triggers model registry init,
    # but that's fine since we only need the schema.
    import os

    os.environ.setdefault("DIRECTAI_API_KEYS", "")
    os.environ.setdefault("DIRECTAI_MODEL_CONFIG_DIR", "deploy/models")

    from app.main import app

    spec = app.openapi()

    # Determine output path
    if args.output:
        out_path = args.output
    elif args.yaml:
        out_path = Path("docs/openapi.yaml")
    else:
        out_path = Path("docs/openapi.json")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.yaml:
        try:
            import yaml
        except ImportError:
            print("ERROR: PyYAML required for YAML export. Install with: pip install pyyaml", file=sys.stderr)
            sys.exit(1)
        out_path.write_text(yaml.dump(spec, default_flow_style=False, sort_keys=False))
    else:
        out_path.write_text(json.dumps(spec, indent=2) + "\n")

    print(f"OpenAPI spec written to {out_path} ({out_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
