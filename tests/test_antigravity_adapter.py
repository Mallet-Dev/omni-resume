"""Tests for the Antigravity session adapter."""

import json
from datetime import datetime

import pytest

from fast_resume.adapters.antigravity import AntigravityAdapter
from fast_resume.adapters.base import Session


@pytest.fixture
def adapter():
    """Create an AntigravityAdapter instance."""
    return AntigravityAdapter()


class TestAntigravityAdapter:
    """Tests for AntigravityAdapter."""

    def test_parse_overview_log(self, adapter, temp_dir):
        """Overview logs should become searchable Antigravity sessions."""
        brain_dir = temp_dir / "brain" / "abc123"
        logs_dir = brain_dir / ".system_generated" / "logs"
        logs_dir.mkdir(parents=True)

        with open(brain_dir / "task.md.metadata.json", "w") as f:
            json.dump(
                {"summary": "Harden lead routing workflow for inbound forms"},
                f,
            )

        overview_file = logs_dir / "overview.txt"
        entries = [
            {
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "created_at": "2026-05-11T18:12:45Z",
                "content": (
                    "<USER_REQUEST>\nFix the lead routing issue\n</USER_REQUEST>\n"
                    "<ADDITIONAL_METADATA>\n"
                    "Active Document: /Users/test/workspace/workflow.json\n"
                    "Running terminal commands:\n"
                    "- hermes (in /Users/test/workspace, running for 2m)\n"
                    "</ADDITIONAL_METADATA>"
                ),
            },
            {
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "created_at": "2026-05-11T18:12:46Z",
                "tool_calls": [{"name": "view_file"}, {"name": "run_command"}],
            },
            {
                "source": "MODEL",
                "type": "AGENT_RESPONSE",
                "created_at": "2026-05-11T18:13:10Z",
                "content": "I patched the workflow and verified the route logic.",
            },
        ]

        with open(overview_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        session = adapter._parse_session_file(overview_file)

        assert session is not None
        assert session.id == "antigravity:abc123"
        assert session.agent == "antigravity"
        assert session.title == "Harden lead routing workflow for inbound forms"
        assert session.directory == "/Users/test/workspace"
        assert "Fix the lead routing issue" in session.content
        assert "[tools: view_file, run_command]" in session.content
        assert "patched the workflow" in session.content
        assert session.timestamp == datetime.fromisoformat("2026-05-11T18:13:10+00:00")

    def test_resume_command_uses_raw_uuid(self, adapter):
        """Antigravity should resume by its native UUID."""
        session = Session(
            id="antigravity:abc123",
            agent="antigravity",
            title="Test",
            directory="/tmp",
            timestamp=datetime.now(),
            content="",
        )

        assert adapter.get_resume_command(session) == ["gemini", "--resume", "abc123"]
