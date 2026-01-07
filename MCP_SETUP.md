# MCP Server Configuration Guide

This guide explains how to properly configure aleph as an MCP server in Cursor, VS Code, and other MCP-compatible editors.

## The Workspace Root Issue

**Problem:** The aleph MCP server defaults to using the current working directory as the workspace root. If you launch Cursor/VS Code from your home directory, aleph will block file operations with:

```
Error: Path '/Volumes/VIXinSSD/aleph/aleph/mcp/local_server.py' escapes workspace root '/Users/hunterbown'
```

**Solution:** Explicitly set the workspace root in your MCP configuration.

## Cursor Configuration

Create or edit `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph-mcp-local",
      "args": [
        "--workspace-root",
        "/Volumes/VIXinSSD/aleph",
        "--enable-actions"
      ]
    }
  }
}
```

### Parameters Explained

- `--workspace-root <path>` - The root directory for file operations (read_file, write_file, run_command, etc.)
- `--enable-actions` - Enable action tools (read_file, write_file, run_command, run_tests, etc.)
- `--require-confirmation` - Require `confirm=true` on all action tool calls
- `--timeout <seconds>` - Sandbox execution timeout (default: 30)
- `--max-output <chars>` - Maximum output characters from commands (default: 10000)

## VS Code Configuration

Create or edit `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph-mcp-local",
      "args": [
        "--workspace-root",
        "/Volumes/VIXinSSD/aleph",
        "--enable-actions"
      ]
    }
  }
}
```

## Finding Your Workspace Root

The workspace root should be the directory containing:
- Your `.git` folder (for git repositories)
- Your `pyproject.toml`, `package.json`, etc.
- The root of your project

**Automatic Detection:** If you don't set `--workspace-root`, aleph will:
1. Check if `.git` exists in current directory
2. If not, search parent directories until finding `.git`
3. Use that directory as the workspace root

**Recommended:** Always set `--workspace-root` explicitly to avoid ambiguity.

## Example Scenarios

### Scenario 1: Python Project

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph-mcp-local",
      "args": [
        "--workspace-root",
        "/Users/yourname/projects/my-python-app",
        "--enable-actions"
      ]
    }
  }
}
```

### Scenario 2: Monorepo

For a monorepo, set workspace to a subdirectory:

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph-mcp-local",
      "args": [
        "--workspace-root",
        "/Users/yourname/monorepo/packages/frontend",
        "--enable-actions"
      ]
    }
  }
}
```

### Scenario 3: Remote Development

For development on remote machines:

```json
{
  "mcpServers": {
    "aleph": {
      "command": "aleph-mcp-local",
      "args": [
        "--workspace-root",
        "/remote/path/to/project",
        "--enable-actions",
        "--timeout",
        "60"
      ]
    }
  }
}
```

## Security Considerations

### Actions Mode

When you enable `--enable-actions`, you grant aleph permission to:
- **Read files** - Read any file in workspace (up to 1MB by default)
- **Write files** - Create/modify files in workspace (up to 1MB by default)
- **Run commands** - Execute shell commands (30s timeout by default)
- **Run tests** - Execute test commands

### Confirmation Mode

Use `--require-confirmation` for safer operation:

```json
{
  "args": [
    "--workspace-root",
        "/path/to/project",
        "--enable-actions",
        "--require-confirmation"
  ]
}
```

When enabled, all action tools require `confirm=true` in the call.

### Adjusting Limits

Customize limits for your use case:

```json
{
  "args": [
    "--workspace-root", "/path/to/project",
    "--enable-actions",
    "--timeout", "60",
    "--max-output", "50000",
    "--max-read-bytes", "5000000",
    "--max-write-bytes", "5000000"
  ]
}
```

Default limits:
- Timeout: 30 seconds
- Max command output: 10,000 characters
- Max file read: 1,000,000 bytes (1MB)
- Max file write: 1,000,000 bytes (1MB)

## Troubleshooting

### "Path escapes workspace root" Error

**Symptom:** File operations fail with path validation error.

**Cause:** Workspace root not set or incorrect.

**Solution:** Add `--workspace-root` to MCP configuration with the correct path.

### "Actions are disabled" Error

**Symptom:** Action tools (read_file, write_file, etc.) return "Actions are disabled."

**Cause:** `--enable-actions` flag not set.

**Solution:** Add `--enable-actions` to MCP configuration.

### MCP Server Not Starting

**Symptom:** Tools don't appear in Cursor/VS Code.

**Possible causes:**
1. aleph not installed: `pip install aleph[mcp]`
2. Entry point not available: Run `aleph-mcp-local --help` to test
3. Python not in PATH: Use full path to python/python3

**Debug steps:**
```bash
# Test if command works
aleph-mcp-local --help

# Check installation
pip show aleph

# Test server manually
python3 -m aleph.mcp.local_server --help
```

## Related Documentation

- [REMOTE_MCP_DIAGNOSIS.md](REMOTE_MCP_DIAGNOSIS.md) - Debugging remote MCP server issues
- [CONFIGURATION.md](docs/CONFIGURATION.md) - Full aleph configuration reference
- [README.md](README.md) - Project overview and installation

## Support

For issues specific to MCP configuration, please check:
1. Your MCP client documentation (Cursor, VS Code, etc.)
2. This configuration guide
3. Remote MCP diagnosis guide

For aleph-specific bugs or feature requests, please open an issue on GitHub.

