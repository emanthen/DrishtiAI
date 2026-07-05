"""Logging filter that redacts sensitive field values from log records.

Prevents passwords, tokens, and secrets from appearing in structured logs
or Loki/stdout — even if a handler accidentally logs a request body.
"""
import logging
import re

_REDACT_RE = re.compile(
    r'(?i)\b(password|passwd|secret|token|api_?key|authorization|access_key|secret_key)'
    r'(\s*[=:]\s*)(\S+)',
)
_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "access_key", "secret_key",
})


def _redact_str(s: str) -> str:
    return _REDACT_RE.sub(r"\1\2***", s)


def _redact_args(args: object) -> object:
    if isinstance(args, dict):
        return {k: "***" if k.lower() in _SENSITIVE_KEYS else v for k, v in args.items()}
    if isinstance(args, tuple):
        return tuple(_redact_str(str(a)) if isinstance(a, str) else a for a in args)
    return args


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact_str(record.msg)
        if record.args:
            record.args = _redact_args(record.args)
        return True
