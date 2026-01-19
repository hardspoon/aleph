# Prompt: Install Aleph Across All Environments

Use this prompt with Claude Code (or any AI assistant with file access) to install Aleph on all your AI coding tools.

---

## Prompt

```
I need you to install and configure Aleph (an MCP server for recursive LLM reasoning over large local data) across all my AI development environments.

**Target environments:**
1. Claude Code (CLI) - via ~/.claude/claude_desktop_config.json or similar
2. Claude Desktop - via ~/Library/Application Support/Claude/claude_desktop_config.json
3. Cursor - via cursor MCP config
4. Windsurf - via windsurf MCP config  
5. Codex CLI - via ~/.codex/config.toml
6. Gemini CLI - via ~/.gemini/mcp.json

**Tasks:**

1. First, check if aleph-rlm is installed:
   ```bash
   pip show aleph-rlm || pip install "aleph-rlm[mcp]"
   ```

2. Run the automatic installer and see what it detects:
   ```bash
   aleph-rlm install
   ```

3. For any environments not auto-detected, manually configure:

   **Claude Desktop** (~/Library/Application Support/Claude/claude_desktop_config.json):
   ```json
   {
      "mcpServers": {
        "aleph": {
          "command": "aleph",
          "args": ["--enable-actions", "--tool-docs", "concise", "--workspace-mode", "git"]
        }
      }
    }
   ```

   **Codex CLI** (~/.codex/config.toml):
   ```toml
   [mcp_servers.aleph]
   command = "aleph"
   args = ["--enable-actions", "--tool-docs", "concise", "--workspace-mode", "git"]
   ```

   **Gemini CLI** (~/.gemini/mcp.json):
   ```json
   {
     "mcpServers": {
       "aleph": {
         "command": "aleph",
         "args": ["--enable-actions", "--tool-docs", "concise", "--workspace-mode", "git"]
       }
     }
   }
   ```

4. Install the `/aleph` skill for Codex CLI:

   ```bash
   mkdir -p ~/.codex/skills/aleph
   cp /path/to/aleph/docs/prompts/aleph.md ~/.codex/skills/aleph/SKILL.md
   ```

5. Configure `sub_query` (optional):

   If you want the API backend, set environment variables:
   ```bash
   export ALEPH_SUB_QUERY_API_KEY=sk-...
   export ALEPH_SUB_QUERY_MODEL=gpt-5.2-codex
   # Optional: OpenAI-compatible base URL (Groq, Together, local LLMs, etc.)
   export ALEPH_SUB_QUERY_URL=https://api.your-provider.com/v1
   ```

   CLI backends (`claude`, `codex`, `gemini`) do not require an API key. Aleph will auto-detect the first available backend unless you set `ALEPH_SUB_QUERY_BACKEND`.

6. Verify installation:
   ```bash
   aleph-rlm doctor
   ```

7. Test by restarting each environment and checking if the aleph tools are available.

**Important notes:**
- The `--enable-actions` flag allows file read/write and command execution
- In CLI environments (Claude Code, Codex, Gemini), `sub_query` can use the local CLI backend - no API key needed
- The installer should handle most of this automatically, but verify each environment works
- For per-project scoping, set `--workspace-root /absolute/path/to/project` instead of `--workspace-mode git`. See MCP_SETUP.md for details.
- Some MCP clients don't reliably pass `env` vars from config to the server process. If `sub_query` reports missing credentials, add exports to your shell profile (~/.zshrc or ~/.bashrc) and restart the client.

Please proceed step by step and report what you find in each environment.
```

---

## What this does

- Installs `aleph-rlm` Python package
- Configures MCP server in all supported AI coding environments
- Optionally sets up OpenAI-compatible API credentials for `sub_query`
- Enables action tools (file I/O, commands) where appropriate
