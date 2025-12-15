"""Run Aleph as an MCP server.

Requires the optional dependency:

    pip install -e '.[mcp]'

Then run:

    python examples/mcp_server.py --provider anthropic --model claude-sonnet-4-20250514

This uses stdio transport.
"""

from __future__ import annotations

import asyncio
import argparse
import sys
from pathlib import Path

# Ensure the repository root is on sys.path when running as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Aleph MCP server")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "openai"])
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    try:
        from aleph.mcp.server import AlephMCPServer
    except Exception as e:
        raise SystemExit(
            "MCP support not installed. Install with `pip install -e '.[mcp]'`\n\n" + str(e)
        )

    model = args.model or ("claude-sonnet-4-20250514" if args.provider == "anthropic" else "gpt-4o")
    server = AlephMCPServer(provider=args.provider, model=model)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
