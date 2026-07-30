#!/usr/bin/env python3
"""Run the x-mutual-pilot CLI from a source checkout."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from x_mutual_pilot.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
