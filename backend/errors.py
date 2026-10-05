from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Raised by services; rendered as {"error": ..., "message": ...}."""

    def __init__(self, status: int, error: str, message: str):
        self.status = status
        self.error = error
        self.message = message


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content={"error": exc.error, "message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return JSONResponse(
            status_code=400,
            content={"error": "INVALID_REQUEST", "message": f"{field}: {first.get('msg', 'invalid input')}"},
        )
