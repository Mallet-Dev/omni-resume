"""Agent adapters for different coding tools."""

from .antigravity import AntigravityAdapter
from .base import (
    AgentAdapter,
    ErrorCallback,
    ParseError,
    RawAdapterStats,
    Session,
    SessionCallback,
)
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .copilot import CopilotAdapter
from .copilot_vscode import CopilotVSCodeAdapter
from .crush import CrushAdapter
from .hermes import HermesAdapter
from .opencode import OpenCodeAdapter
from .vibe import VibeAdapter

__all__ = [
    "AntigravityAdapter",
    "AgentAdapter",
    "ErrorCallback",
    "ParseError",
    "RawAdapterStats",
    "Session",
    "SessionCallback",
    "ClaudeAdapter",
    "CodexAdapter",
    "CopilotAdapter",
    "CopilotVSCodeAdapter",
    "CrushAdapter",
    "HermesAdapter",
    "OpenCodeAdapter",
    "VibeAdapter",
]
