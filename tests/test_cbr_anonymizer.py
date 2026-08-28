from app.services.cbr_anonymizer import anonymize_text


def test_anonymizer_redacts_rfc_and_email() -> None:
    result = anonymize_text(
        "Contacto persona@example.com con RFC ABCD010203XYZ."
    )
    assert "persona@example.com" not in result.text
    assert "ABCD010203XYZ" not in result.text
    assert result.redaction_count == 2
    assert result.requires_human_review is True


def test_anonymizer_never_claims_complete_anonymization() -> None:
    result = anonymize_text("Texto sin identificadores detectados.")
    assert result.redaction_count == 0
    assert result.requires_human_review is True
