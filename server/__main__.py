"""Entry point for running the PlayPalace v11 server."""

import asyncio
import sys

from .core.server import run_server


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
