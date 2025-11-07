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
        request_data = data_processor.parse_request_body(event)
        user_chat = request_data['user_chat']
        user_info = request_data['user_info']

        # bedrock 플래그를 body에서 직접 읽어옴
        body = json.loads(event.get('body', '{}'))
        use_bedrock = body.get('bedrock', False)

        locations = data_processor.extract_locations(user_chat)
        embedding = llm_service.get_embedding(user_chat)

        classification_prompt = prompts.get_classification_prompt(user_chat)
        intent_str = llm_service.get_llm_response(classification_prompt, use_bedrock=use_bedrock)
        intent = data_processor.parse_intent(intent_str)
        logger.info(f"사용자 의도 분류: {intent}") # 'WELFARE' or 'EMPLOYMENT'

        # 의도에 따라 분기하여 DB 검색
        # search_results_raw의 형식은 intent에 따라 다름
        search_results_raw, result_type = database.search_services(intent, embedding, locations)

        # 검색 결과를 표준 포맷으로 정규화
        # (name, summary, url, prov, city) 튜플의 리스트로 통일됨
        normalized_results = data_processor.normalize_results(search_results_raw, result_type)

        # 결과 재순위화 (기존 로직 재사용)
        final_results_tuples = data_processor.rerank_results(normalized_results, locations)

        if not final_results_tuples:
            # 정책 -> 정책이나 정보
            body = {'answer': '문의하신 내용과 관련된 정책이나 정보를 찾을 수 없습니다.', 'services': []}
            return data_processor.build_response(200, body)

        # LLM 프롬프트 생성
        context_str = data_processor.format_context_string(final_results_tuples)

        # 프롬프트에 검색 컨텍스트(의도) 주입
        final_prompt = prompts.get_final_prompt(
            context_str=context_str,
            user_info=user_info,
            user_chat=user_chat,
            search_type=intent # "WELFARE" or "EMPLOYMENT"
        )

        # LLM 호출 및 응답 파싱
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

