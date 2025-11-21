# lambda_function.py
import json
import logging
import re

import database
import llm_service
import prompts
import data_processor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    메인 핸들러: 경로(path)에 따라 검색 또는 리프레이밍 로직으로 분기합니다.
    """
    logger.info(f"이벤트 수신: {event}")

    # API Gateway로부터 전달된 path 확인
    # (로컬 테스트나 직접 호출 시 path가 없을 수 있으므로 .get 사용)
    path = event.get('path', '')
    http_method = event.get('httpMethod', '')

    try:
        # (/chatbot/reframing - POST)
        if 'reframing' in path and http_method == 'POST':
            return handle_reframing_request(event)

        # 복지/구인 검색 요청 처리
        return handle_search_request(event)

    except Exception as e:
        logger.error(f"핸들러 실행 중 예측하지 못한 오류 발생: {e}", exc_info=True)
        return data_processor.build_response(500, {'error': '서버 내부 오류가 발생했습니다.'})

def handle_reframing_request(event):
    """
    리프레이밍(Reframing) 요청을 처리하는 핸들러
    """
    try:
        # 1. 입력 파싱 (data_processor 업데이트 필요)
        user_input = data_processor.parse_reframing_body(event)

        # 2. 프롬프트 생성 (prompts/reframing.py 사용)
        prompt = prompts.get_reframing_prompt(user_input)

        # 3. LLM 호출 (Gemini 사용 강제: use_bedrock=False)
        llm_response_str = llm_service.get_llm_response(prompt, use_bedrock=False)

        # 4. JSON 파싱
        json_match = re.search(r'\{.*\}', llm_response_str, re.DOTALL)
        if not json_match:
            # JSON 형식이 아닐 경우 텍스트 그대로 반환 (오류 처리)
            response_data = {
                "empathy": "형식에 맞지 않는 응답이 생성되었습니다.",
                "reframed_thought": llm_response_str
            }
        else:
            response_data = json.loads(json_match.group(0))

        return data_processor.build_response(200, response_data)

    except ValueError as e:
        logger.warning(f"리프레이밍 잘못된 요청: {e}")
        return data_processor.build_response(400, {'error': str(e)})
    except Exception as e:
        logger.error(f"리프레이밍 로직 오류: {e}")
        raise e

def handle_search_request(event):
    """
    기존 복지/구인 정보 RAG 검색을 처리하는 핸들러
    """
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
        norm_welfare = data_processor.normalize_results(welfare_results, "WELFARE")
        norm_employment = data_processor.normalize_results(employment_results, "EMPLOYMENT")

        # 모든 결과를 score(거리 점수) 기준으로 정렬 (낮을수록 관련성 높음)
        all_normalized_results = norm_welfare + norm_employment
        sorted_results = sorted(all_normalized_results, key=lambda x: x[0]) # x[0]이 score

        # 상위 3개만 추출 (RAG 컨텍스트)
        top_3_with_scores = sorted_results[:3]

        # (name, summary, url, prov, city) 튜플의 리스트로 변환
        top_3_tuples = [item[1] for item in top_3_with_scores]

        # 결과 재순위화
        # 벡터 점수 상위 3개 내에서 지역명으로 추가 재순위화
        final_results_tuples = data_processor.rerank_results(top_3_tuples, locations)

        if not final_results_tuples:
            body = {'answer': '문의하신 내용과 관련된 정책이나 정보를 찾을 수 없습니다.', 'services': []}
            return data_processor.build_response(200, body)

        # LLM 프롬프트 생성
        context_str = data_processor.format_context_string(final_results_tuples)

        # [변경] 패키지화된 프롬프트 함수 호출 (get_final_prompt -> get_search_prompt)
        final_prompt = prompts.get_search_prompt(context_str, user_info, user_chat)

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
