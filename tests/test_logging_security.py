from app.core.logging import redact_log_text


def test_log_redaction_masks_common_secret_shapes() -> None:
    message = (
        "Authorization: Bearer abc123 "
        "api_key=xyz password=hunter2 secret=private"
    )
    redacted = redact_log_text(message)
    assert "abc123" not in redacted
    assert "xyz" not in redacted
    assert "hunter2" not in redacted
    assert "private" not in redacted
    assert redacted.count("[REDACTED]") == 4
