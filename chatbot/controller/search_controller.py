# chatbot/controller/search_controller.py
from fastapi import APIRouter, Depends
from chatbot.schema.search import SearchRequest, SearchResponse
from chatbot.domain.search_logic import SearchService, get_search_service

router = APIRouter(tags=["Welfare Search"])

@router.post(
    "/chatbot/query",
    response_model=SearchResponse,
    summary="복지/구인 정보 검색",
    description="사용자의 질문과 개인 정보(선택)를 입력받아, 관련된 복지 정책이나 채용 공고를 검색하고 답변을 생성합니다."
)
def search_endpoint(
        request: SearchRequest,
        service: SearchService = Depends(get_search_service)
):
    return service.execute_search(
        user_chat=request.query2,
        user_info=request.query1,
        use_bedrock=request.bedrock
    )
