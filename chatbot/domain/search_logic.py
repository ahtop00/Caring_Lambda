# chatbot/domain/search_logic.py
import logging
import json
import re
from fastapi import HTTPException, Depends

from service.llm_service import LLMService, get_llm_service
from repository.search_repository import SearchRepository, get_search_repository
from util import response_builder
from prompts.search import get_search_prompt

logger = logging.getLogger()

class SearchService:
    def __init__(self, search_repo: SearchRepository, llm_service: LLMService):
        self.search_repo = search_repo
        self.llm_service = llm_service

    def execute_search(self, user_chat: str, user_info: str, use_bedrock: bool) -> dict:
        """
        검색(RAG) 비즈니스 로직
        """
        try:
            # 임베딩 및 지역 추출
            locations = response_builder.extract_locations(user_chat)

            # 임베딩 생성
            embedding = self.llm_service.get_embedding(user_chat)

            # DB 검색
            welfare_results = self.search_repo.search_welfare_services(embedding, locations)
            employment_results = self.search_repo.search_employment_jobs(embedding)

            logger.info(f"검색 결과: 복지 {len(welfare_results)}건, 채용 {len(employment_results)}건")

            # 결과 정규화 및 통합
            norm_welfare = response_builder.normalize_results(welfare_results, "WELFARE")
            norm_employment = response_builder.normalize_results(employment_results, "EMPLOYMENT")

            all_results = sorted(norm_welfare + norm_employment, key=lambda x: x[0])
            top_3_tuples = [item[1] for item in all_results[:3]]

            # 재순위화
            final_results = response_builder.rerank_results(top_3_tuples, locations)

            if not final_results:
                return {'answer': '관련 정보를 찾을 수 없습니다.', 'services': []}

            # LLM 호출
            context_str = response_builder.format_context_string(final_results)
            prompt = get_search_prompt(context_str, user_info, user_chat)

            # 답변 생성
            llm_response = self.llm_service.get_llm_response(prompt, use_bedrock=use_bedrock)

            # 결과 파싱
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if not json_match:
                logger.error(f"LLM 응답 파싱 실패: {llm_response}")
                return {
                    'answer': "죄송합니다. 답변 생성 중 일시적인 오류가 발생했습니다.",
                    'services': []
                }

            return json.loads(json_match.group(0))

        except Exception as e:
            logger.error(f"시스템 오류: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

# --- 의존성 주입용 함수 ---
def get_search_service(
        search_repo: SearchRepository = Depends(get_search_repository),
        llm_service: LLMService = Depends(get_llm_service)
) -> SearchService:
    return SearchService(search_repo, llm_service)
