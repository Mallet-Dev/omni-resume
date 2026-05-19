"""Tests for the Hermes session adapter."""

import json
from datetime import datetime

import pytest

from fast_resume.adapters.base import Session
from fast_resume.adapters.hermes import HermesAdapter


@pytest.fixture
def adapter():
    """Create a HermesAdapter instance."""
    return HermesAdapter()


class TestHermesAdapter:
    """Tests for HermesAdapter."""

    def test_parse_jsonl_session(self, adapter, temp_dir):
        """JSONL transcripts should produce searchable Hermes sessions."""
        session_file = temp_dir / "20260519_013246_f5a269.jsonl"
        entries = [
            {"role": "session_meta", "session_id": "20260519_013246_f5a269"},
            {
                "role": "user",
                "content": "Please update /Users/test/workspace/README.md",
            },
            {"role": "assistant", "content": "I updated the README."},
        ]

        with open(session_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        session = adapter._parse_session_file(session_file)

        assert session is not None
        assert session.id == "hermes:20260519_013246_f5a269"
        assert session.agent == "hermes"
        assert session.directory == "/Users/test/workspace"
        assert "Please update" in session.title
        assert "I updated the README" in session.content
        assert session.message_count == 2

    def test_parse_json_export(self, adapter, temp_dir):
        """Saved JSON exports should also be indexed."""
        session_file = temp_dir / "session_20260508_164844_f8b01d.json"
        payload = {
            "session_id": "20260508_164844_f8b01d",
            "session_start": "2026-05-08T16:48:44.358547",
            "last_updated": "2026-05-08T16:50:52.175745",
            "messages": [
                {"role": "user", "content": "Check /Users/test/project/app.py"},
                {"role": "assistant", "content": "The file looks good."},
            ],
        }

        with open(session_file, "w") as f:
            json.dump(payload, f)

        session = adapter._parse_session_file(session_file)

        assert session is not None
        assert session.id == "hermes:20260508_164844_f8b01d"
        assert session.directory == "/Users/test/project"
        assert session.timestamp == datetime.fromisoformat("2026-05-08T16:50:52.175745")

    def test_resume_command_uses_raw_id(self, adapter):
        """Resume commands should strip the internal session prefix."""
        session = Session(
            id="hermes:20260519_013246_f5a269",
            agent="hermes",
            title="Test",
            directory="/tmp",
            timestamp=datetime.now(),
            content="",
        )

        assert adapter.get_resume_command(session) == [
            "hermes",
            "--resume",
            "20260519_013246_f5a269",
        ]
        assert adapter.get_resume_command(session, yolo=True) == [
            "hermes",
            "--yolo",
            "--resume",
            "20260519_013246_f5a269",
        ]
