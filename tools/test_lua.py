#!/usr/bin/env python3
"""Run the DCS-runtime Lua 5.1 mock tests (requires pytest and Lua 5.1)."""
from pathlib import Path
import os
import shutil
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    lua = os.environ.get("LUA51") or shutil.which("lua5.1") or shutil.which("lua")
    if not lua:
        print("Lua 5.1 is required. Install it or set LUA51 to its executable.", file=sys.stderr)
        return 2
    result = subprocess.run([lua, "-v"], capture_output=True, text=True)
    if result.returncode or "Lua 5.1" not in result.stdout + result.stderr:
        print("The runtime tests require Lua 5.1; set LUA51 to a Lua 5.1 executable.", file=sys.stderr)
        return 2
    environment = dict(os.environ, LUA51=lua)
    return subprocess.call([sys.executable, "-m", "pytest", "-q",
                            str(root / "tests" / "test_runtime.py"), *sys.argv[1:]],
                           cwd=root, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
