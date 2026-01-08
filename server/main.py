"""Entry point for running the PlayPalace v11 server with uv run main.py."""

import asyncio
import sys
import os

# Ensure we can import from the package correctly
_script_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_script_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# Change to script directory so relative paths work
os.chdir(_script_dir)

from server.core.server import run_server  # noqa: E402


def main():
    """Main entry point."""
    host = "0.0.0.0"
    port = 8000

    # Parse command line arguments
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    if len(sys.argv) > 2:
        host = sys.argv[2]

    print(f"Starting PlayPalace v11 server on {host}:{port}")
    asyncio.run(run_server(host, port))


if __name__ == "__main__":
    main()
