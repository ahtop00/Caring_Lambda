# lambda_function.py
import json
import logging
import re
# 자체 모듈 임포트
import database
import llm_service
import prompts
import data_processor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info(f"이벤트 수신: {event}")
    try:
        # 요청 처리 및 데이터 추출
        request_data = data_processor.parse_request_body(event)
        user_chat = request_data['user_chat']
        user_info = request_data['user_info']

        body = json.loads(event.get('body', '{}'))
        use_bedrock = body.get('bedrock', False)

        # 검색을 위한 데이터 준비
        locations = data_processor.extract_locations(user_chat)
        embedding = llm_service.get_embedding(user_chat)

        # 두 테이블을 모두 검색합니다.
        welfare_results = database.search_welfare_services(embedding, locations)
        employment_results = database.search_employment_jobs(embedding)

        logger.info(f"DB 검색 결과: 복지 {len(welfare_results)}건, 고용 {len(employment_results)}건")

        # 두 검색 결과를 정규화하고 'score' 기준으로 통합

        # normalize_results가 (score, (name, summary, ...)) 튜플 리스트를 반환
        norm_welfare = data_processor.normalize_results(welfare_results, "WELFARE")
        norm_employment = data_processor.normalize_results(employment_results, "EMPLOYMENT")

        # 모든 결과를 score(거리 점수) 기준으로 정렬 (낮을수록 관련성 높음)
        all_normalized_results = norm_welfare + norm_employment
        sorted_results = sorted(all_normalized_results, key=lambda x: x[0]) # x[0]이 score

        # 5. 상위 3개만 추출 (RAG 컨텍스트)
        # top_3_with_scores = [ (score, (name, ...)), ... ]
        top_3_with_scores = sorted_results[:3]

        # (name, summary, url, prov, city) 튜플의 리스트로 변환
        top_3_tuples = [item[1] for item in top_3_with_scores]

        # 결과 재순위화
        # 벡터 점수 상위 3개 내에서 지역명으로 추가 재순위화
        final_results_tuples = data_processor.rerank_results(top_3_tuples, locations)

        if not final_results_tuples:
            body = {'answer': '문의하신 내용과 관련된 정책이나 정보를 찾을 수 없습니다.', 'services': []}
            return data_processor.build_response(200, body)

        # LLM 프롬프트 생성 (단순화된 프롬프트 사용)
        context_str = data_processor.format_context_string(final_results_tuples)
        final_prompt = prompts.get_final_prompt(context_str, user_info, user_chat)
        llm_response_str = llm_service.get_llm_response(final_prompt, use_bedrock=use_bedrock)

        json_match = re.search(r'\{.*\}', llm_response_str, re.DOTALL)
        if not json_match:
            raise ValueError("LLM 응답에서 JSON 객체를 찾지 못했습니다.")

        response_data = json.loads(json_match.group(0))

        # 최종 응답 반환
        return data_processor.build_response(200, response_data)

    except ValueError as e:
        logger.warning(f"잘못된 요청: {e}")
        return data_processor.build_response(400, {'error': str(e)})
    except Exception as e:
        logger.error(f"핸들러 실행 중 예측하지 못한 오류 발생: {e}", exc_info=True)
        return data_processor.build_response(500, {'error': '서버 내부 오류가 발생했습니다.'})
