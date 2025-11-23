# chatbot/exception/handler.py
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .definition import AppError

logger = logging.getLogger()

async def app_exception_handler(request: Request, exc: AppError):
    """우리가 정의한 비즈니스 예외 처리"""
    logger.error(f"AppError 발생: {exc.message} ({exc.detail})")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": exc.status_code,
            "message": exc.message,
            "detail": exc.detail
        }
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """FastAPI 기본 HTTPException 처리 (404 Not Found 등)"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": exc.status_code,
            "message": exc.detail,
            "detail": None
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic 유효성 검사 실패 처리 (422)"""
    error_msg = ""
    for error in exc.errors():
        error_msg += f"{error['loc'][-1]}: {error['msg']}; "

    logger.warning(f"유효성 검사 실패: {error_msg}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "code": 422,
            "message": "요청 데이터가 올바르지 않습니다.",
            "detail": error_msg.strip()
        }
    )

async def global_exception_handler(request: Request, exc: Exception):
    """그 외 모든 예측하지 못한 시스템 에러 처리 (500)"""
    logger.error(f"시스템 알 수 없는 오류: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "code": 500,
            "message": "서버 내부 오류가 발생했습니다.",
            "detail": str(exc)
        }
    )
