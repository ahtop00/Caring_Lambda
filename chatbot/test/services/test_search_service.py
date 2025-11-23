# chatbot/test/services/test_search_service.py
import pytest
import json
from unittest.mock import Mock
from domain.search_logic import SearchService
from repository.search_repository import SearchRepository
from service.llm_service import LLMService

def test_execute_search_success():
    """
    [Scenario] 검색 결과가 있을 때 정상적으로 LLM 답변까지 생성하는지 테스트
    """
    # 1. Mock 준비
    mock_repo = Mock(spec=SearchRepository)
    mock_llm = Mock(spec=LLMService)

    # 2. 데이터 설정
    # (2-1) 임베딩 생성 성공
    mock_llm.get_embedding.return_value = [0.1, 0.2, 0.3]

    # (2-2) DB 검색 결과 (Score, Name, Summary, Link, Province, City)
    mock_repo.search_welfare_services.return_value = [
        (0.1, "청년 수당", "매월 50만원", "http://link", "서울", "강남구")
    ]
    mock_repo.search_employment_jobs.return_value = []

    # (2-3) LLM 답변 설정
    mock_llm.get_llm_response.return_value = json.dumps({
        "answer": "서울 강남구 청년 수당이 있습니다.",
        "services": [{"service_name": "청년 수당", "summary": "...", "url": "..."}]
    })

    # 3. 실행
    service = SearchService(search_repo=mock_repo, llm_service=mock_llm)
    result = service.execute_search("서울 청년 복지", "20대 무직", use_bedrock=False)

    # 4. 검증
    assert result["answer"] == "서울 강남구 청년 수당이 있습니다."
    mock_repo.search_welfare_services.assert_called_once()

def test_execute_search_no_results():
    """
    [Scenario] DB 검색 결과가 없을 때 바로 반환하는지 테스트
    """
    mock_repo = Mock(spec=SearchRepository)
    mock_llm = Mock(spec=LLMService)

    mock_llm.get_embedding.return_value = [0.1]
    mock_repo.search_welfare_services.return_value = []
    mock_repo.search_employment_jobs.return_value = []

    service = SearchService(search_repo=mock_repo, llm_service=mock_llm)
    result = service.execute_search("없는거 찾아줘", "", False)

    assert "찾을 수 없습니다" in result["answer"]
    # 결과가 없으면 LLM 호출을 안 해야 함
    mock_llm.get_llm_response.assert_not_called()
