"""Start the local frontend against the existing Rahtal database and real model."""

from pathlib import Path
import runpy
import sys


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    namespace = runpy.run_path(str(root / "examples" / "web" / "server.py"))
    return namespace["main"](["--rahtal", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
