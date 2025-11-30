# chatbot/controller/search_controller.py
import logging
from fastapi import APIRouter, Depends
from schema.search import SearchRequest, SearchResponse
from domain.search_logic import SearchService, get_search_service
from schema.common import COMMON_RESPONSES

logger = logging.getLogger()
router = APIRouter(tags=["Welfare Search"])

@router.post(
    "/chatbot/query",
    response_model=SearchResponse,
    summary="복지/구인 정보 검색",
    description="사용자의 질문과 개인 정보(선택)를 입력받아, 관련된 복지 정책이나 채용 공고를 검색하고 답변을 생성합니다.",
    responses=COMMON_RESPONSES
)
def search_endpoint(
        request: SearchRequest,
        service: SearchService = Depends(get_search_service)
):
    """복지/구인 정보 검색 엔드포인트"""
    logger.info(f"검색 요청 시작 - query2: {request.query2[:50]}..., bedrock: {request.bedrock}")
    try:
        result = service.execute_search(
            user_chat=request.query2,
            user_info=request.query1,
            use_bedrock=request.bedrock
        )
        logger.info(f"검색 요청 완료 - 결과 수: {len(result.results) if hasattr(result, 'results') else 'N/A'}")
        return result
    except Exception as e:
        logger.error(
            f"검색 요청 실패 - query2: {request.query2[:50]}..., error: {e}",
            exc_info=True
        )
        raise
