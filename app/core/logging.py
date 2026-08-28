import logging
import re
from logging.config import dictConfig

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)[^\s,;]+"),
)


def redact_log_text(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


class SecretRedactionFilter(logging.Filter):
    """Redacta secretos comunes sin registrar el contenido fiscal de consultas."""

    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage()
        record.msg = redact_log_text(rendered)
        record.args = ()
        return True


def configure_logging(level: str) -> None:
    """Configura logging sin registrar secretos ni contenido fiscal del usuario."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
                }
            },
            "filters": {
                "redact_secrets": {
                    "()": "app.core.logging.SecretRedactionFilter",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": level,
                    "filters": ["redact_secrets"],
                }
            },
            "root": {"handlers": ["console"], "level": level},
        }
    )
    logging.getLogger(__name__).info("Logging configurado")
