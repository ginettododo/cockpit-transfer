from __future__ import annotations

import sys

from .cli import run_cli
from .gui import launch_gui


def main() -> int:
    if len(sys.argv) > 1:
        return run_cli()
    launch_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
