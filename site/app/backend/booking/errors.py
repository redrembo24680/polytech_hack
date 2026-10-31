from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _resp(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return _resp(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errs = exc.errors()
        if errs:
            first = errs[0]
            loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
            msg = f"{loc}: {first.get('msg')}" if loc else str(first.get("msg"))
        else:
            msg = "invalid request"
        return _resp(422, "validation", msg)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return _resp(404, "not_found", "not found")
        return _resp(exc.status_code, "error", str(exc.detail))
