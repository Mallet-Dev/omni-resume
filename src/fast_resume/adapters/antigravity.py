"""Antigravity session adapter."""

from datetime import datetime
from pathlib import Path
import re

import orjson

from ..config import AGENTS, ANTIGRAVITY_BRAIN_DIR
from ..logging_config import log_parse_error
from .base import BaseSessionAdapter, ErrorCallback, ParseError, Session, truncate_title

ABSOLUTE_PATH_RE = re.compile(r"(/(?:Users|home)/[^\s\"'<>]+)")
ACTIVE_DOCUMENT_RE = re.compile(r"Active Document:\s*([^\n]+)")
TERMINAL_CWD_RE = re.compile(r"\(in ([^)]+), running")
USER_REQUEST_RE = re.compile(
    r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", re.DOTALL | re.IGNORECASE
)


class AntigravityAdapter(BaseSessionAdapter):
    """Adapter for Antigravity brain sessions."""

    name = "antigravity"
    color = AGENTS["antigravity"]["color"]
    badge = AGENTS["antigravity"]["badge"]
    supports_yolo = False

    def __init__(self, sessions_dir: Path | None = None) -> None:
        self._sessions_dir = (
            sessions_dir if sessions_dir is not None else ANTIGRAVITY_BRAIN_DIR
        )

    def find_sessions(self) -> list[Session]:
        """Find all Antigravity sessions."""
        if not self.is_available():
            return []

        sessions = []
        for overview in self._iter_overview_files():
            session = self._parse_session_file(overview)
            if session:
                sessions.append(session)

        return sessions

    def _iter_overview_files(self) -> list[Path]:
        """Return overview logs for each Antigravity brain."""
        return sorted(self._sessions_dir.glob("*/.system_generated/logs/overview.txt"))

    def _scan_session_files(self) -> dict[str, tuple[Path, float]]:
        """Scan Antigravity overview logs."""
        current_files: dict[str, tuple[Path, float]] = {}

        for overview in self._iter_overview_files():
            try:
                mtime = self._session_mtime(overview)
            except OSError:
                continue

            session_id = self._normalize_id(overview.parents[2].name)
            current_files[session_id] = (overview, mtime)

        return current_files

    def _session_mtime(self, overview: Path) -> float:
        """Use the newest relevant artifact as the session mtime."""
        candidates = [
            overview,
            overview.parents[2] / "task.md",
            overview.parents[2] / "task.md.metadata.json",
            overview.parents[2] / "walkthrough.md",
            overview.parents[2] / "walkthrough.md.metadata.json",
        ]
        mtimes = [path.stat().st_mtime for path in candidates if path.exists()]
        return max(mtimes) if mtimes else overview.stat().st_mtime

    def _parse_session_file(
        self, session_file: Path, on_error: ErrorCallback = None
    ) -> Session | None:
        """Parse an Antigravity overview log."""
        try:
            brain_dir = session_file.parents[2]
            raw_id = brain_dir.name
            messages: list[str] = []
            user_prompts: list[str] = []
            path_hints: list[str] = []
            timestamp = datetime.fromtimestamp(self._session_mtime(session_file))
            turn_count = 0

            with open(session_file, "rb") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = orjson.loads(line)
                    except orjson.JSONDecodeError:
                        continue

                    source = entry.get("source", "")
                    entry_type = entry.get("type", "")

                    if source == "USER_EXPLICIT" and entry_type == "USER_INPUT":
                        text = self._extract_user_request(entry.get("content", ""))
                        if text:
                            messages.append(f"» {text}")
                            user_prompts.append(text)
                            turn_count += 1
                        path_hints.extend(self._collect_path_hints(entry.get("content", "")))
                        created_at = entry.get("created_at")
                        if created_at:
                            timestamp = self._parse_timestamp(created_at)
                    elif source == "MODEL" and entry_type in {
                        "PLANNER_RESPONSE",
                        "AGENT_RESPONSE",
                    }:
                        text = self._extract_model_text(entry)
                        if text:
                            messages.append(f"  {text}")
                            turn_count += 1
                        created_at = entry.get("created_at")
                        if created_at:
                            timestamp = self._parse_timestamp(created_at)

            if not user_prompts:
                return None

            title = self._load_title(brain_dir, user_prompts[0])
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

    def _load_title(self, brain_dir: Path, fallback_prompt: str) -> str:
        """Build the session title from task metadata or the first prompt."""
        metadata_path = brain_dir / "task.md.metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, "rb") as f:
                    metadata = orjson.loads(f.read())
                summary = metadata.get("summary", "")
                if summary:
                    return truncate_title(summary, max_length=80, word_break=False)
            except (OSError, orjson.JSONDecodeError):
                pass

        return truncate_title(fallback_prompt, max_length=80, word_break=False)

    def _extract_user_request(self, content: str) -> str:
        """Extract the plain user request from Antigravity wrapper text."""
        match = USER_REQUEST_RE.search(content)
        if match:
            return match.group(1).strip()
        return content.strip()

    def _extract_model_text(self, entry: dict) -> str:
        """Extract searchable text from a model response entry."""
        content = entry.get("content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()

        tool_calls = entry.get("tool_calls", [])
        if isinstance(tool_calls, list) and tool_calls:
            names = []
            for tool_call in tool_calls:
                name = tool_call.get("name")
                if name:
                    names.append(name)
            if names:
                joined = ", ".join(names[:6])
                if len(names) > 6:
                    joined += ", ..."
                return f"[tools: {joined}]"

        return ""

    def _collect_path_hints(self, content: str) -> list[str]:
        """Find usable project paths embedded in Antigravity metadata."""
        hints: list[str] = []

        for regex in (ACTIVE_DOCUMENT_RE, TERMINAL_CWD_RE):
            for match in regex.finditer(content):
                candidate = match.group(1).strip()
                if candidate:
                    hints.append(candidate)

        hints.extend(match.group(1) for match in ABSOLUTE_PATH_RE.finditer(content))
        return hints

    def _best_directory(self, hints: list[str]) -> str:
        """Pick the best project directory from collected hints."""
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
        """Parse Antigravity ISO timestamps."""
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _normalize_id(self, raw_id: str) -> str:
        """Prefix session IDs to avoid cross-agent collisions."""
        return f"{self.name}:{raw_id}"

    def get_resume_command(self, session: Session, yolo: bool = False) -> list[str]:
        """Fallback to Antigravity's native session listing for the project."""
        return ["gemini", "--list-sessions"]
