# chatbot/schema/common.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ErrorResponse(BaseModel):
    """전역 예외 핸들러가 반환하는 에러 응답 포맷"""
    error: bool = Field(default=True, description="에러 발생 여부 (항상 True)", json_schema_extra={"example": True})
    code: int = Field(..., description="HTTP 상태 코드")
    message: str = Field(..., description="에러 메시지")
    detail: Optional[str] = Field(None, description="상세 에러 내용 (Traceback 등)")

def _build_error_response(status_code: int, description: str, message_example: str, detail_example: str = None):
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "example": {
                    "error": True,
                    "code": status_code,
                    "message": message_example,
                    "detail": detail_example
                }
            }
        }
    }

# [수정] 프로젝트 실제 로직에 맞춘 현실적인 에러 예시 정의
COMMON_RESPONSES: Dict[int, Dict[str, Any]] = {
    400: _build_error_response(
        400,
        "잘못된 요청 (Bad Request)",
        "요청 파라미터가 올바르지 않습니다."
    ),
    404: _build_error_response(
        404,
        "데이터 없음 (Not Found)",
        "해당 기간에 대화 기록이 없어 리포트를 생성할 수 없습니다.",
        "ReportService: No logs found for user_id=test_user"
    ),
    422: _build_error_response(
        422,
        "유효성 검사 실패 (Validation Error)",
        "필수 필드가 누락되었습니다.",
        "body.user_input: field required"  # 실제 ReframingRequest의 필드 사용
    ),
    500: _build_error_response(
        500,
        "서버 내부 오류 (Internal Server Error)",
        "상담 답변을 생성하는 중 오류가 발생했습니다.",
        "LLMServiceError: Bedrock API connection timed out" # LLM 관련 실제 에러 상황 예시
    ),
}
