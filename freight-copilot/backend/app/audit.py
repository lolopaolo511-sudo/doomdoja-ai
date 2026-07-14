"""Audit logging and secret redaction helpers.

Every consequential action and agent run is recorded. Logs are scrubbed of
anything that looks like a secret or obvious personal contact detail before
being written, per the privacy requirements.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditEvent

_SECRET_KEYS = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|bearer|client[_-]?secret)"
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def redact(value: Any) -> Any:
    """Recursively redact secrets / emails from a structure destined for logs."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if _SECRET_KEYS.search(str(k)):
                out[k] = "***REDACTED***"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _EMAIL.sub("***@***", value)
    return value


def record(
    session: Session,
    *,
    action: str,
    actor: str = "system",
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=redact(detail or {}),
    )
    session.add(event)
    return event
