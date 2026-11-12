"""RFC 9457 problem+json errors and RateLimit headers for /v1 (API-03).

The body keeps a `detail` string, which is what existing clients already read, and adds `type`, `title` and `status`. Validation errors (422)
also carry an `errors` list. Nothing about the request is echoed back except what FastAPI already reports.
"""
from __future__ import annotations

from http import HTTPStatus

from fastapi.responses import JSONResponse

PROBLEM = "application/problem+json"


def title_for(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Error"


def problem(status: int, detail, *, headers: dict | None = None, errors: list | None = None) -> JSONResponse:
    # `detail` stays exactly what the handler raised (a string, or a small object such as {"code": "mfa_required"}) so existing clients keep working.
    body: dict = {"type": "about:blank", "title": title_for(status), "status": status, "detail": detail}
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, headers=headers, media_type=PROBLEM)


def rate_headers(limit: int, remaining: int) -> dict[str, str]:
    return {"RateLimit-Limit": str(limit), "RateLimit-Remaining": str(max(0, remaining)), "RateLimit-Reset": "60"}
