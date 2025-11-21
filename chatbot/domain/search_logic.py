# chatbot/domain/search_logic.py
import logging
import json
import re

# 모듈 import
from service import db_service, llm_service
from util import request_parser, response_builder
from prompts.search import get_search_prompt

logger = logging.getLogger()

def process_search(event):
    """검색 요청(RAG) 처리 메인 로직"""
    try:
        # 1. 요청 파싱
        req_data = request_parser.parse_search_request(event)
        user_chat = req_data['user_chat']
        user_info = req_data['user_info']
        use_bedrock = req_data['use_bedrock']

        # 2. 임베딩 및 지역 추출
        locations = request_parser.extract_locations(user_chat)
        embedding = llm_service.get_embedding(user_chat)

        # 3. DB 검색
        welfare_results = db_service.search_welfare_services(embedding, locations)
        employment_results = db_service.search_employment_jobs(embedding)

        logger.info(f"검색 결과: 복지 {len(welfare_results)}건, 채용 {len(employment_results)}건")

        # 4. 결과 정규화 및 통합
        norm_welfare = response_builder.normalize_results(welfare_results, "WELFARE")
        norm_employment = response_builder.normalize_results(employment_results, "EMPLOYMENT")

        all_results = sorted(norm_welfare + norm_employment, key=lambda x: x[0])
        top_3_tuples = [item[1] for item in all_results[:3]]

        # 5. 재순위화 (지역 기반)
        final_results = response_builder.rerank_results(top_3_tuples, locations)

        if not final_results:
            body = {'answer': '관련 정보를 찾을 수 없습니다.', 'services': []}
            return response_builder.build_response(200, body)

        # 6. LLM 호출
        context_str = response_builder.format_context_string(final_results)
        prompt = get_search_prompt(context_str, user_info, user_chat)
        llm_response = llm_service.get_llm_response(prompt, use_bedrock=use_bedrock)

        # 7. 결과 파싱
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if not json_match:
            raise ValueError("LLM 응답 형식이 JSON이 아닙니다.")

        response_data = json.loads(json_match.group(0))
        return response_builder.build_response(200, response_data)

    except ValueError as e:
        logger.warning(f"요청 오류: {e}")
        return response_builder.build_response(400, {'error': str(e)})
    except Exception as e:
        logger.error(f"시스템 오류: {e}", exc_info=True)
        return response_builder.build_response(500, {'error': 'Internal Server Error'})
