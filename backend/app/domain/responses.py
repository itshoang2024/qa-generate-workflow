from typing import Any
from uuid import uuid4


def envelope(data: Any = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {"request_id": f"req_{uuid4().hex[:12]}"},
        "error": error,
    }


def error_envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return envelope(
        data=None,
        error={
            "code": code,
            "message": message,
            "details": details,
        },
    )

