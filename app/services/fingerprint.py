from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_ISO_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_MEMORY_ADDRESS_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
_HEX_RE = re.compile(r"\b(?<!0x)[0-9a-fA-F]{12,}\b")
_REQUEST_ID_RE = re.compile(
    r"\b(request[_\- ]?id|req[_\- ]?id|trace[_\- ]?id)\b[:= ]*([A-Za-z0-9._:\-]+)",
    re.IGNORECASE,
)
_LONG_NUMBER_RE = re.compile(r"\b\d{5,}\b")
_LABEL_NUMBER_RE = re.compile(
    r"\b(id|user_id|record_id|db_id|request_id|trace_id|line)[:= ]+(\d+)\b",
    re.IGNORECASE,
)
_STACK_LINE_RE = re.compile(
    r"(?P<prefix>File \"(?P<path>[^\"]+)\", line )(?P<line>\d+)(?P<suffix>, in .+)"
)


@dataclass(frozen=True)
class FingerprintInput:
    service_name: str
    normalized_message: str
    exception_type: str | None
    stack_trace: str | None


def _normalize_common(text: str) -> str:
    normalized = text.strip()
    normalized = _UUID_RE.sub("<uuid>", normalized)
    normalized = _ISO_TIMESTAMP_RE.sub("<timestamp>", normalized)
    normalized = _ISO_DATE_RE.sub("<date>", normalized)
    normalized = _EMAIL_RE.sub("<email>", normalized)
    normalized = _IP_RE.sub("<ip>", normalized)
    normalized = _MEMORY_ADDRESS_RE.sub("<memory_address>", normalized)
    normalized = _REQUEST_ID_RE.sub(lambda match: f"{match.group(1)}:<request_id>", normalized)
    normalized = _LABEL_NUMBER_RE.sub(lambda match: f"{match.group(1)}=<id>", normalized)
    normalized = _HEX_RE.sub("<hex>", normalized)
    normalized = _LONG_NUMBER_RE.sub("<number>", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_message(message: str) -> str:
    return _normalize_common(message)


def normalize_stack_trace(stack_trace: str | None) -> str:
    if stack_trace is None:
        return ""

    normalized_lines: list[str] = []
    for raw_line in stack_trace.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = _STACK_LINE_RE.sub(
            lambda match: f"{match.group('prefix')}<line>{match.group('suffix')}",
            line,
        )
        line = _normalize_common(line)
        line = re.sub(r":\d+", ":<line>", line)
        normalized_lines.append(line)
    return "\n".join(normalized_lines)


def generate_fingerprint(payload: FingerprintInput) -> str:
    parts = [
        payload.service_name.strip().lower(),
        payload.normalized_message,
        (payload.exception_type or "").strip().lower(),
        normalize_stack_trace(payload.stack_trace),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest
