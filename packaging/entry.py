"""Entry point of the Windows build: start Inferno Ghostwriter and open it in the browser."""

import sys

from inferno_ghostwriter import main

if __name__ == "__main__":
    if "--open" not in sys.argv:
        sys.argv.append("--open")
    main()
