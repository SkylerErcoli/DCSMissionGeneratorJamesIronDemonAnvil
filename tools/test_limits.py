#!/usr/bin/env python3
"""Run option-boundary and aircraft-capability regression checks."""
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    return subprocess.call([sys.executable, "-m", "pytest", "-q",
                            str(root / "tests" / "test_model.py"), *sys.argv[1:]], cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
