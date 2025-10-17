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

        # bedrock 플래그를 body에서 직접 읽어옴
        body = json.loads(event.get('body', '{}'))
        use_bedrock = body.get('bedrock', False)

        # 검색을 위한 데이터 준비
        locations = data_processor.extract_locations(user_chat)
        embedding = llm_service.get_embedding(user_chat)

        # 데이터베이스 검색
        search_results = database.search_welfare_services(embedding, locations)

        # 결과 재순위화
        final_results = data_processor.rerank_results(search_results, locations)

        if not final_results:
            body = {'answer': '문의하신 내용과 관련된 정책을 찾을 수 없습니다.', 'services': []}
            return data_processor.build_response(200, body)

        # LLM 프롬프트 생성
        context_str = data_processor.format_context_string(final_results)
        final_prompt = prompts.get_final_prompt(context_str, user_info, user_chat)

        # LLM 호출 및 응답 파싱
        # get_anthropic_response -> get_llm_response로 변경하고 use_bedrock 플래그 전달
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
