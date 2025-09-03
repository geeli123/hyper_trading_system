import logging
import os
import traceback

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .response import ApiResponse


class GlobalExceptionHandler(BaseHTTPMiddleware):
    """全局异常处理中间件"""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException as http_exc:
            return JSONResponse(content=ApiResponse.error(message=http_exc.detail))
        except Exception as exc:
            error_msg = str(exc)
            error_traceback = traceback.format_exc()
            logging.error(f"未处理的异常: {error_msg}")
            logging.error(f"异常堆栈: {error_traceback}")
            if os.getenv('DEBUG', 'False').lower() == 'true':
                detailed_error = f"{error_msg}\n\n堆栈跟踪:\n{error_traceback}"
            else:
                detailed_error = "服务器内部错误，请稍后重试"
            return JSONResponse(content=ApiResponse.error(message=detailed_error))


def setup_exception_handlers(app):
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(content=ApiResponse.error(message=exc.detail))

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        error_msg = str(exc)
        error_traceback = traceback.format_exc()
        logging.error(f"未处理的异常: {error_msg}")
        logging.error(f"异常堆栈: {error_traceback}")
        if os.getenv('DEBUG', 'False').lower() == 'true':
            detailed_error = f"{error_msg}\n\n堆栈跟踪:\n{error_traceback}"
        else:
            detailed_error = "服务器内部错误，请稍后重试"
        return JSONResponse(content=ApiResponse.error(message=detailed_error))
