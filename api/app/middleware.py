from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        # Order data (incl. Drive link) must never be cached by browsers or proxies.
        h["Cache-Control"] = "no-store"
        if get_settings().is_production:
            h.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response
