# chatbot/domain/search_logic.py
import logging
import json
import re
from fastapi import HTTPException

from service import db_service, llm_service
from util import response_builder
from prompts.search import get_search_prompt

logger = logging.getLogger()

def execute_search(user_chat: str, user_info: str, use_bedrock: bool) -> dict:
    """
    검색(RAG) 비즈니스 로직
    :return: 결과 Dict (SearchResponse 구조)
    """
    try:
        # 1. 임베딩 및 지역 추출 (response_builder에 통합된 함수 사용)
        locations = response_builder.extract_locations(user_chat)
        embedding = llm_service.get_embedding(user_chat)

        # 2. DB 검색
        welfare_results = db_service.search_welfare_services(embedding, locations)
        employment_results = db_service.search_employment_jobs(embedding)

        logger.info(f"검색 결과: 복지 {len(welfare_results)}건, 채용 {len(employment_results)}건")

        # 3. 결과 정규화 및 통합
        norm_welfare = response_builder.normalize_results(welfare_results, "WELFARE")
        norm_employment = response_builder.normalize_results(employment_results, "EMPLOYMENT")

        all_results = sorted(norm_welfare + norm_employment, key=lambda x: x[0])
        top_3_tuples = [item[1] for item in all_results[:3]]

        # 4. 재순위화
        final_results = response_builder.rerank_results(top_3_tuples, locations)

        if not final_results:
            return {'answer': '관련 정보를 찾을 수 없습니다.', 'services': []}

        # 5. LLM 호출
        context_str = response_builder.format_context_string(final_results)
        prompt = get_search_prompt(context_str, user_info, user_chat)
        llm_response = llm_service.get_llm_response(prompt, use_bedrock=use_bedrock)

        # 6. 결과 파싱
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if not json_match:
            logger.error(f"LLM 응답 파싱 실패: {llm_response}")
            # 사용자에게 에러 대신 안내 문구 반환
            return {
                'answer': "죄송합니다. 답변 생성 중 일시적인 오류가 발생했습니다.",
                'services': []
            }

        return json.loads(json_match.group(0))

    except Exception as e:
        logger.error(f"시스템 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
