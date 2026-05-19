<p align="center">
  <img src="assets/logo.png" alt="omni-resume" width="120" height="120">
</p>

# omni-resume

Unified search and resume for coding-agent session history.

`omni-resume` is a public fork/extension of [fast-resume](https://github.com/angristan/fast-resume) focused on real multi-agent setups. It keeps the fast local search experience, adds support for Hermes and Antigravity, and stays honest about where each agent can resume directly versus where the native CLI only supports a project-scoped fallback.

It is an operator tool, not a memory layer. Use it to find and reopen past work. Pair it with something like Honcho if you also want shared cross-agent memory and profile-building.

![demo](https://github.com/user-attachments/assets/5ea9c2a5-a7c0-41bf-9357-394aeaaa0a06)

## Why this exists

Most agent CLIs can resume a session, but very few let you search your actual conversation history well.

That gets worse once you spread work across multiple surfaces:

- Claude Code
- Codex
- Hermes
- Antigravity / Gemini CLI
- OpenCode
- Copilot
- Vibe

`omni-resume` puts those histories behind one fast TUI and one Tantivy index so you can search first and hand off second.

## What it does

- Full-text search across supported agent histories
- Fast incremental indexing with Tantivy
- Searchable message content, not just titles
- One TUI for all supported agents
- Native resume where the agent exposes a stable session identifier
- Explicit fallbacks where the agent does not

## Support matrix

| Agent | Indexed | Resume behaviour |
| --- | --- | --- |
| Claude Code | Yes | Direct resume |
| Codex | Yes | Direct resume |
| Hermes | Yes | Direct resume |
| OpenCode | Yes | Direct resume |
| Copilot CLI | Yes | Direct resume |
| Copilot VS Code | Yes | Opens project context |
| Vibe | Yes | Direct resume |
| Crush | Yes | Project reopen fallback |
| Antigravity | Yes | Native session-list fallback |

### Antigravity note

Antigravity's current CLI does not expose a stable public "resume by exact session id" contract the way Claude, Codex, and Hermes do. `omni-resume` still indexes Antigravity cleanly, but handoff currently falls back to:

```bash
gemini --list-sessions
```

run from the original project directory.

That means Antigravity support is useful today for search and project recovery, but not yet a perfect one-click exact resume.

## Added in this fork

- Hermes adapter for `~/.hermes/sessions`
- Antigravity adapter for `~/.gemini/antigravity/brain/*/.system_generated/logs/overview.txt`
- Hermes direct resume support via `hermes --resume <session_id>`
- Antigravity project-aware fallback using its native session picker flow
- Rebranded package, cache path, and CLI metadata for standalone public use

## Installation

### From GitHub

```bash
uv tool install git+https://github.com/Mallet-Dev/omni-resume
```

This installs:

- `omni-resume`
- `fr`

`fr` is kept as the short alias.

### From source

```bash
git clone https://github.com/Mallet-Dev/omni-resume.git
cd omni-resume
uv sync
uv run omni-resume
```

## Usage

### Open the TUI

```bash
omni-resume
```

or:

```bash
fr
```

### Filter by agent

```bash
fr -a codex
fr -a hermes
fr -a antigravity
```

### Search inline

```bash
fr "auth bug"
fr "agent:codex date:<1d migration"
fr "agent:hermes workspace memory"
fr "agent:antigravity lead routing"
```

### List sessions without the TUI

```bash
fr --list
fr --no-tui
fr --stats
fr --rebuild
```

## Yolo support

Agents with explicit yolo or bypass support continue to use it:

| Agent | Yolo support |
| --- | --- |
| Claude | Yes |
| Codex | Yes |
| Hermes | Yes |
| Copilot CLI | Yes |
| Vibe | Yes |
| OpenCode | Config-based |
| Antigravity | Not wired yet in resume fallback |
| Crush | No |

## Default storage paths

| Agent | Path |
| --- | --- |
| Claude | `~/.claude/projects` |
| Codex | `~/.codex/sessions` |
| Hermes | `~/.hermes/sessions` |
| Antigravity | `~/.gemini/antigravity/brain` |
| OpenCode | `~/.local/share/opencode` |
| Copilot CLI | `~/.copilot/session-state` |
| Vibe | `~/.vibe/logs/session` |

Index and parse logs are stored in:

```bash
~/.cache/omni-resume
```

## Development

```bash
git clone https://github.com/Mallet-Dev/omni-resume.git
cd omni-resume
uv sync
uv run pytest -v
```

Targeted adapter checks:

```bash
uv run pytest tests/test_hermes_adapter.py -q
uv run pytest tests/test_antigravity_adapter.py -q
```

## Roadmap

- Exact Antigravity resume once the CLI exposes a stable session identifier
- Additional agent adapters for teams running more than one IDE surface
- Better packaging and release automation for Homebrew and PyPI
- Optional per-workspace wrappers for noisy global installs

## Credits

This project builds directly on [fast-resume](https://github.com/angristan/fast-resume) by [@angristan](https://github.com/angristan). The core search/index architecture and TUI foundation come from that project; this fork extends the adapter layer and public positioning for broader multi-agent workflows.
