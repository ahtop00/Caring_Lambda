# chatbot/lambda_function.py
import logging
from util.response_builder import build_response
from domain.search_logic import process_search
from domain.reframing_logic import process_reframing

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    메인 핸들러: 라우팅만 담당
    """
    path = event.get('path', '')
    http_method = event.get('httpMethod', '')
    logger.info(f"요청 수신 - Path: {path}, Method: {http_method}")

    try:
        # 리프레이밍 요청
        if 'reframing' in path and http_method == 'POST':
            return process_reframing(event)

        # 검색(Query) 요청
        elif ('query' in path or path == '/chatbot') and http_method == 'POST':
            return process_search(event)

        # 404 Not Found
        else:
            return build_response(404, {'error': 'Not Found: 알 수 없는 경로입니다.'})

    except Exception as e:
        logger.error(f"핸들러 치명적 오류: {e}", exc_info=True)
        return build_response(500, {'error': 'Server Error'})
