# chatbot/schema/common.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ErrorResponse(BaseModel):
    """전역 예외 핸들러가 반환하는 에러 응답 포맷"""
    error: bool = Field(default=True, description="에러 발생 여부 (항상 True)", example=True)
    code: int = Field(..., description="HTTP 상태 코드", example=500)
    message: str = Field(..., description="에러 메시지", example="서버 내부 오류가 발생했습니다.")
    detail: Optional[str] = Field(None, description="상세 에러 내용 (Traceback 등)", example="ZeroDivisionError: division by zero")

# Swagger(@router)에 쉽게 적용하기 위한 공통 응답 정의
# 필요한 에러 코드만 골라서 사용할 수도 있습니다.
COMMON_RESPONSES: Dict[int, Dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "잘못된 요청 (Bad Request)"},
    401: {"model": ErrorResponse, "description": "인증 실패 (Unauthorized)"},
    404: {"model": ErrorResponse, "description": "리소스를 찾을 수 없음 (Not Found)"},
    422: {"model": ErrorResponse, "description": "유효성 검사 실패 (Validation Error)"},
    500: {"model": ErrorResponse, "description": "서버 내부 오류 (Internal Server Error)"},
}
