from __future__ import annotations

from app.services.fingerprint import (
    FingerprintInput,
    generate_fingerprint,
    normalize_message,
    normalize_stack_trace,
)


def test_normalize_message_replaces_common_dynamic_values() -> None:
    message = (
        "User 12345 requested /items/98765 at 2026-07-22T10:11:12Z from 10.1.2.3 "
        "trace_id=abc123def4567890 request_id=req-123e4567-e89b-12d3-a456-426614174000 "
        "email=test.user@example.com address=0x7ffdeadbeef value=abcdef1234567890"
    )

    normalized = normalize_message(message)

    assert "<number>" in normalized
    assert "<timestamp>" in normalized
    assert "<ip>" in normalized
    assert "<request_id>" in normalized
    assert "<email>" in normalized
    assert "<memory_address>" in normalized
    assert "<hex>" in normalized


def test_normalize_stack_trace_replaces_line_numbers() -> None:
    stack_trace = (
        '  File "/app/app/services/logs.py", line 42, in ingest_log\n'
        '  File "/app/app/repositories/log.py", line 108, in create_log'
    )

    normalized = normalize_stack_trace(stack_trace)

    assert "line <line>" in normalized


def test_generate_fingerprint_is_deterministic_for_similar_errors() -> None:
    base = FingerprintInput(
        service_name="billing-api",
        normalized_message="failed to save record <id>",
        exception_type="IntegrityError",
        stack_trace='File "/app/app/services/logs.py", line 42, in ingest_log',
    )
    variant = FingerprintInput(
        service_name="billing-api",
        normalized_message="failed to save record <id>",
        exception_type="IntegrityError",
        stack_trace='File "/app/app/services/logs.py", line 99, in ingest_log',
    )

    assert generate_fingerprint(base) == generate_fingerprint(variant)


def test_generate_fingerprint_separates_unrelated_errors() -> None:
    first = FingerprintInput(
        service_name="billing-api",
        normalized_message="failed to save record <id>",
        exception_type="IntegrityError",
        stack_trace="trace one",
    )
    second = FingerprintInput(
        service_name="billing-api",
        normalized_message="failed to fetch record <id>",
        exception_type="LookupError",
        stack_trace="trace two",
    )

    assert generate_fingerprint(first) != generate_fingerprint(second)
