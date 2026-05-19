"""Hermes session adapter."""

from datetime import datetime
from pathlib import Path
import re

import orjson

from ..config import AGENTS, HERMES_DIR
from ..logging_config import log_parse_error
from .base import BaseSessionAdapter, ErrorCallback, ParseError, Session, truncate_title

ABSOLUTE_PATH_RE = re.compile(r"(/(?:Users|home)/[^\s\"'<>]+)")


class HermesAdapter(BaseSessionAdapter):
    """Adapter for Hermes sessions."""

    name = "hermes"
    color = AGENTS["hermes"]["color"]
    badge = AGENTS["hermes"]["badge"]
    supports_yolo = True

    def __init__(self, sessions_dir: Path | None = None) -> None:
        self._sessions_dir = sessions_dir if sessions_dir is not None else HERMES_DIR

    def find_sessions(self) -> list[Session]:
        """Find all Hermes sessions."""
        if not self.is_available():
            return []

        sessions = []
        for session_file in self._iter_session_files():
            session = self._parse_session_file(session_file)
            if session:
                sessions.append(session)

        return sessions

    def _iter_session_files(self) -> list[Path]:
        """Return candidate session files."""
        return sorted(
            [
                *self._sessions_dir.rglob("*.jsonl"),
                *self._sessions_dir.rglob("*.json"),
            ]
        )

    def _scan_session_files(self) -> dict[str, tuple[Path, float]]:
        """Scan all Hermes session files."""
        current_files: dict[str, tuple[Path, float]] = {}

        for session_file in self._iter_session_files():
            try:
                mtime = session_file.stat().st_mtime
            except OSError:
                continue

            session_id = self._get_session_id_from_file(session_file)
            if not session_id:
                continue

            existing = current_files.get(session_id)
            if existing is None or mtime >= existing[1]:
                current_files[session_id] = (session_file, mtime)

        return current_files

    def _get_session_id_from_file(self, session_file: Path) -> str:
        """Extract the normalized session id from file content or filename."""
        raw_id = ""

        try:
            if session_file.suffix == ".jsonl":
                with open(session_file, "rb") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            data = orjson.loads(line)
                        except orjson.JSONDecodeError:
                            continue
                        if data.get("role") == "session_meta":
                            raw_id = data.get("session_id", "") or session_file.stem
                            break
            else:
                with open(session_file, "rb") as f:
                    data = orjson.loads(f.read())
                raw_id = data.get("session_id", "")
        except (OSError, orjson.JSONDecodeError):
            raw_id = ""

        if not raw_id:
            raw_id = session_file.stem
            if raw_id.startswith("session_"):
                raw_id = raw_id.removeprefix("session_")

        return self._normalize_id(raw_id)

    def _parse_session_file(
        self, session_file: Path, on_error: ErrorCallback = None
    ) -> Session | None:
        """Parse a Hermes session file."""
        try:
            if session_file.suffix == ".jsonl":
                return self._parse_jsonl_session(session_file)
            return self._parse_json_session(session_file)
        except OSError as e:
            error = ParseError(
                agent=self.name,
                file_path=str(session_file),
                error_type="OSError",
                message=str(e),
            )
            log_parse_error(
                error.agent, error.file_path, error.error_type, error.message
            )
            if on_error:
                on_error(error)
            return None
        except (KeyError, TypeError, AttributeError, ValueError) as e:
            error = ParseError(
                agent=self.name,
                file_path=str(session_file),
                error_type=type(e).__name__,
                message=str(e),
            )
            log_parse_error(
                error.agent, error.file_path, error.error_type, error.message
            )
            if on_error:
                on_error(error)
            return None

    def _parse_jsonl_session(self, session_file: Path) -> Session | None:
        """Parse a Hermes JSONL transcript."""
        raw_id = session_file.stem
        messages: list[str] = []
        user_prompts: list[str] = []
        path_hints: list[str] = []
        turn_count = 0
        timestamp = datetime.fromtimestamp(session_file.stat().st_mtime)

        with open(session_file, "rb") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue

                role = data.get("role", "")
                if role == "session_meta":
                    raw_id = data.get("session_id", raw_id) or raw_id
                    path_hints.extend(self._collect_path_hints(data))
                    continue

                text = self._extract_text(data.get("content"))
                if role == "user":
                    if text:
                        messages.append(f"» {text}")
                        user_prompts.append(text)
                        turn_count += 1
                    path_hints.extend(self._collect_path_hints(data))
                elif role == "assistant":
                    if text:
                        messages.append(f"  {text}")
                        turn_count += 1
                    path_hints.extend(self._collect_path_hints(data))

        if not user_prompts:
            return None

        title = truncate_title(user_prompts[0], max_length=80, word_break=False)
        directory = self._best_directory(path_hints)

        return Session(
            id=self._normalize_id(raw_id),
            agent=self.name,
            title=title,
            directory=directory,
            timestamp=timestamp,
            content="\n\n".join(messages),
            message_count=turn_count,
        )

    def _parse_json_session(self, session_file: Path) -> Session | None:
        """Parse a Hermes JSON transcript export."""
        with open(session_file, "rb") as f:
            data = orjson.loads(f.read())

        raw_id = data.get("session_id", "") or session_file.stem
        timestamp = self._parse_timestamp(
            data.get("last_updated")
            or data.get("session_start")
            or datetime.fromtimestamp(session_file.stat().st_mtime).isoformat()
        )

        messages: list[str] = []
        user_prompts: list[str] = []
        path_hints = self._collect_path_hints(data)
        turn_count = 0

        for message in data.get("messages", []):
            role = message.get("role", "")
            text = self._extract_text(message.get("content"))
            if role == "user":
                if text:
                    messages.append(f"» {text}")
                    user_prompts.append(text)
                    turn_count += 1
            elif role == "assistant":
                if text:
                    messages.append(f"  {text}")
                    turn_count += 1
            path_hints.extend(self._collect_path_hints(message))

        if not user_prompts:
            return None

        title = truncate_title(user_prompts[0], max_length=80, word_break=False)
        directory = self._best_directory(path_hints)

        return Session(
            id=self._normalize_id(raw_id),
            agent=self.name,
            title=title,
            directory=directory,
            timestamp=timestamp,
            content="\n\n".join(messages),
            message_count=turn_count,
        )

    def _extract_text(self, value) -> str:
        """Flatten Hermes content payloads into searchable text."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts = [self._extract_text(item) for item in value]
            return "\n".join(part for part in parts if part).strip()
        if isinstance(value, dict):
            if "text" in value and isinstance(value["text"], str):
                return value["text"].strip()

            collected: list[str] = []
            for key in (
                "content",
                "input_text",
                "output_text",
                "summary_text",
                "reasoning",
                "reasoning_content",
            ):
                if key in value:
                    text = self._extract_text(value[key])
                    if text:
                        collected.append(text)
            return "\n".join(collected).strip()
        return ""

    def _collect_path_hints(self, value) -> list[str]:
        """Find path-like values inside structured payloads."""
        hints: list[str] = []

        if isinstance(value, str):
            hints.extend(match.group(1) for match in ABSOLUTE_PATH_RE.finditer(value))
        elif isinstance(value, list):
            for item in value:
                hints.extend(self._collect_path_hints(item))
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {"encrypted_content"}:
                    continue
                if key in {"cwd", "directory", "working_directory", "path"} and isinstance(
                    item, str
                ):
                    hints.append(item)
                else:
                    hints.extend(self._collect_path_hints(item))

        return hints

    def _best_directory(self, hints: list[str]) -> str:
        """Pick the best usable directory from collected hints."""
        for hint in hints:
            path = Path(hint).expanduser()
            if path.is_dir():
                return str(path)
            if path.exists():
                return str(path.parent)
            if path.suffix:
                return str(path.parent)
            if hint.startswith("/"):
                return str(path)
        return ""

    def _parse_timestamp(self, value: str) -> datetime:
        """Parse Hermes ISO timestamps."""
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    def _normalize_id(self, raw_id: str) -> str:
        """Prefix session IDs to avoid cross-agent collisions."""
        return f"{self.name}:{raw_id}"

    def _raw_id(self, session_id: str) -> str:
        """Strip the adapter prefix from a normalized session ID."""
        prefix = f"{self.name}:"
        return session_id[len(prefix) :] if session_id.startswith(prefix) else session_id

    def get_resume_command(self, session: Session, yolo: bool = False) -> list[str]:
        """Get command to resume a Hermes session."""
        cmd = ["hermes"]
        if yolo:
            cmd.append("--yolo")
        cmd.extend(["--resume", self._raw_id(session.id)])
        return cmd
