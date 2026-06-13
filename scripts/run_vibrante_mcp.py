#!/usr/bin/env python
"""
Vibrante Runtime — MCP stdio entry point
=========================================
Run this script to expose the Vibrante Runtime as an MCP server over stdio.
Claude Desktop, Codex CLI, Cursor, and any MCP-compatible client can connect
to Houdini's procedural scene graph through the Vibrante semantic layer.

All execution routes through:
    ValidationEngine → RuntimeConstraints → TransactionManager → houdini_runtime

Raw Houdini mutation APIs are never exposed directly.

──────────────────────────────────────────────────────────────────────────────
Claude Code  (CLI / VS Code — stored in ~/.claude.json, or project .mcp.json)
──────────────────────────────────────────────────────────────────────────────

    claude mcp add-json vibrante '{
      "command": "python",
      "args": ["D:/Vibrante-Node/source/scripts/run_vibrante_mcp.py"]
    }' --scope user

Note: Claude Code ignores a "mcpServers" key in ~/.claude/settings.json —
use `claude mcp add` (user scope) or a .mcp.json file (project scope).

──────────────────────────────────────────────────────────────────────────────
Claude Desktop  (Settings → Developer → Edit Config:
  Windows %APPDATA%/Claude/claude_desktop_config.json,
  macOS   ~/Library/Application Support/Claude/claude_desktop_config.json)
──────────────────────────────────────────────────────────────────────────────

    {
      "mcpServers": {
        "vibrante": {
          "command": "python",
          "args": ["D:/Vibrante-Node/source/scripts/run_vibrante_mcp.py"]
        }
      }
    }

If Houdini is running with the Vibrante-Node plugin, set the bridge port:

    {
      "mcpServers": {
        "vibrante": {
          "command": "python",
          "args": ["D:/Vibrante-Node/source/scripts/run_vibrante_mcp.py"],
          "env": { "VIBRANTE_HOU_PORT": "18811" }
        }
      }
    }

──────────────────────────────────────────────────────────────────────────────
Codex CLI  (codex.toml or ~/.config/codex/config.toml)
──────────────────────────────────────────────────────────────────────────────

    [mcp_servers.vibrante]
    command     = "python"
    args        = ["D:/Vibrante-Node/source/scripts/run_vibrante_mcp.py"]
    trust_level = "trusted"

──────────────────────────────────────────────────────────────────────────────
Cursor  (.cursor/mcp.json in workspace root or ~/.cursor/mcp.json globally)
──────────────────────────────────────────────────────────────────────────────

    {
      "mcpServers": {
        "vibrante": {
          "command": "python",
          "args": ["D:/Vibrante-Node/source/scripts/run_vibrante_mcp.py"]
        }
      }
    }

──────────────────────────────────────────────────────────────────────────────
Prerequisites
──────────────────────────────────────────────────────────────────────────────

  pip install "mcp>=1.0.0" pydantic toposort

For Houdini scene operations:
  1. Open Houdini with the Vibrante-Node plugin installed.
  2. Click Vibrante-Node → Launch Vibrante-Node from the Houdini menu.
     The bridge server starts automatically on port 18811.
  3. Run this script — tools like query_scene_context will connect to it.

Without Houdini, planning/knowledge tools work fully; scene/execution
tools return a clear "bridge not available" message.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Ensure the project root is importable as `src`
# ---------------------------------------------------------------------------

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---------------------------------------------------------------------------
# Import runtime layer (lazy — nothing heavy loaded until first tool call)
# ---------------------------------------------------------------------------

from src.runtime.mcp_transport    import MCPTransport
from src.runtime.mcp_tool_registry import register_all_tools
from src.runtime.runtime_bootstrap import initialize_runtime

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    transport = MCPTransport()

    # Warm up runtime singletons (fast — just touches the singleton instances)
    initialize_runtime()

    # Register all 11 semantic orchestration tools
    register_all_tools(transport)

    # Block and serve over stdio
    transport.run_stdio()
