# Changelog

## 0.5.7

- Switched Codex CLI sub-queries to `codex exec --full-auto`, with stdin support for long prompts.
- Added auto-reconnect for remote MCP servers and a configurable default timeout (`ALEPH_REMOTE_TOOL_TIMEOUT`).

## 0.5.6

- Removed deprecated recipe workflow and aider backend references.
- Added Gemini CLI sub-query backend and updated backend priority docs.
- Improved sub-query system prompt for structured output.
- Added Full Power Mode docs and made installer defaults max power.
- Added `--max-write-bytes` and aligned file size limits across docs.
- Clarified action-tool file size caps and workspace mode usage.
