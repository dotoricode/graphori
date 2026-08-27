"""``python -m graphori_core`` entry point for the generic terminal adapter CLI."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
