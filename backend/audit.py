"""Append-only audit trail at output/audit_trail.json.

The file is one JSON object with a growing "records" list. Each append
takes a file lock, re-reads the file, adds one record and atomically
replaces the file, so earlier history is never dropped and the file is
always valid JSON. If the file exists but is not valid JSON, appends stop
with an error instead of overwriting it.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import AUDIT_FILE
from .models import AuditRecord

SCHEMA = "campus-customs-audit/v1"
MAX_STRING_CHARS = 2_000
_SECRET_KEY_NAMES = re.compile(r"(api[_-]?key|authorization|token|secret|password)", re.I)


class AuditError(RuntimeError):
    pass


def _redact(value: Any, secrets: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if _SECRET_KEY_NAMES.search(str(k)) else _redact(v, secrets)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(v, secrets) for v in value]
    if isinstance(value, str):
        for s in secrets:
            value = value.replace(s, "[REDACTED]")
        if len(value) > MAX_STRING_CHARS:
            value = value[:MAX_STRING_CHARS] + f"... [truncated {len(value) - MAX_STRING_CHARS} chars]"
    return value


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON to a temp file in the same directory, then rename it over
    `path`, so readers never see a half-written file. Callers hold a lock."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class AuditTrail:
    def __init__(self, run_id: str, path: Path = AUDIT_FILE):
        self.run_id = run_id
        self.path = path
        self._lock_path = path.parent / f".{path.name}.lock"
        # Values that must never reach the file, even if a model echoes them.
        self._secrets = tuple(v for v in (os.environ.get("PORTKEY_API_KEY"),) if v)

    def _load(self) -> dict:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return {"schema": SCHEMA, "note": "Append-only. Never edit or truncate.", "records": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AuditError(
                f"{self.path} is not valid JSON ({exc}). Refusing to overwrite audit history; "
                "repair or move the file aside before running the team again."
            ) from exc
        if not isinstance(data, dict) or not isinstance(data.get("records"), list):
            raise AuditError(f"{self.path} does not have a top-level 'records' list.")
        return data

    def append(self, *, event: str, ticket_id: int | None, agent: str | None = None, **fields: Any) -> AuditRecord:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._lock_path, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = self._load()
            record = AuditRecord(
                seq=len(data["records"]) + 1,
                timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                run_id=self.run_id,
                ticket_id=ticket_id,
                agent=agent,
                event=event,
                **fields,
            )
            data["records"].append(_redact(record.model_dump(mode="json", exclude_none=True), self._secrets))
            atomic_write_json(self.path, data)
        return record
