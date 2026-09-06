"""Same-origin deployment defaults and safe server-error responses."""
import logging
import os

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)
SERVER_ERROR = "Unable to complete this request. Please try again later."


def install_http_security(app):
    origins = [value.strip() for value in os.getenv(
        "CORS_ALLOWED_ORIGINS", "https://vps.tailc0d72c.ts.net"
    ).split(",") if value.strip()]
    if any("*" in origin for origin in origins):
        raise RuntimeError("CORS_ALLOWED_ORIGINS must contain explicit origins")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        if error.status_code >= 500:
            logger.error("Server HTTP error status=%s path=%s", error.status_code, request.url.path)
            return JSONResponse({"detail": SERVER_ERROR}, status_code=error.status_code)
        return JSONResponse({"detail": error.detail}, status_code=error.status_code, headers=error.headers)

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        # Exception strings can contain SQL, credentials or provider responses.
        logger.error("Unhandled server error type=%s path=%s", type(error).__name__, request.url.path)
        return JSONResponse({"detail": SERVER_ERROR}, status_code=500)
