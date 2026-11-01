"""Command-Line Interface (CLI) for Maritime Tail Risk Engine.

Root wrapper delegating to maritime_risk.cli.main.
"""

from __future__ import annotations

import sys
from maritime_risk.cli import main

if __name__ == "__main__":
    sys.exit(main())
