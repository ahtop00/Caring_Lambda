# chatbot/test/services/test_report_service.py
import pytest
import json
from unittest.mock import Mock
from datetime import date

from schema.history import WeeklyReportResponse
from domain.report_logic import ReportService
from repository.report_repository import ReportRepository
from service.llm_service import LLMService
from exception import AppError

def test_generate_weekly_report_success():
    """
    [Scenario] 정상적인 대화 로그와 LLM 응답이 있을 때 리포트 생성 성공 테스트
    """
    # 1. Mock 객체 생성
    mock_repo = Mock(spec=ReportRepository)
    mock_llm = Mock(spec=LLMService)

    # 2. 가짜 데이터 설정
    # (2-1) 대화 로그가 존재함
    mock_repo.get_logs_by_period.return_value = [
        ("힘들어", {"empathy": "그랬군요"}, date(2023, 10, 1)),
        ("기뻐", {"empathy": "좋네요"}, date(2023, 10, 2))
    ]

    # (2-2) LLM이 정상 JSON 반환
    llm_response_dict = {
        "title": "성장 소설",
        "content": "주인공은 성장했다.",
        "emotions": {"기쁨": 1, "슬픔": 1}
    }
    mock_llm.get_llm_response.return_value = json.dumps(llm_response_dict)

    # (2-3) DB 저장 성공 (ID 1 반환)
    mock_repo.save_weekly_report.return_value = 1

    # 3. 서비스 초기화
    service = ReportService(report_repo=mock_repo, llm_service=mock_llm)

    # 4. 실행
    target_date = date(2023, 10, 4) # 수요일
    result = service.generate_weekly_report("user_1", target_date)

    # 5. 검증
    assert isinstance(result, WeeklyReportResponse)
    assert result.report_id == 1
    assert result.title == "성장 소설"
    # 저장 메서드가 호출되었는지 확인
    mock_repo.save_weekly_report.assert_called_once()

def test_generate_weekly_report_no_logs():
    """
    [Scenario] 기간 내 대화 로그가 없으면 404 AppError가 발생해야 함
    """
    mock_repo = Mock(spec=ReportRepository)
    mock_llm = Mock(spec=LLMService)

    # 로그 없음 ([])
    mock_repo.get_logs_by_period.return_value = []

    service = ReportService(report_repo=mock_repo, llm_service=mock_llm)

    # 404 에러 발생 확인
    with pytest.raises(AppError) as exc_info:
        service.generate_weekly_report("user_1", date(2023, 10, 4))

    assert exc_info.value.status_code == 404
    assert "대화 기록이 없어" in exc_info.value.message

def test_generate_weekly_report_parsing_error():
    """
    [Scenario] LLM이 이상한 응답을 줘서 파싱에 실패해도, 에러 없이 '생성 실패' 리포트를 저장해야 함
    """
    mock_repo = Mock(spec=ReportRepository)
    mock_llm = Mock(spec=LLMService)

    # 로그 있음
    mock_repo.get_logs_by_period.return_value = [("안녕", {}, date(2023, 10, 1))]

    # LLM이 깨진 JSON 반환
    bad_response = "이것은 JSON이 아닙니다."
    mock_llm.get_llm_response.return_value = bad_response

    # DB 저장 성공 가정
    mock_repo.save_weekly_report.return_value = 2

    service = ReportService(report_repo=mock_repo, llm_service=mock_llm)

    # 실행 (에러가 안 나야 성공)
    result = service.generate_weekly_report("user_1", date(2023, 10, 4))

    # 검증
    assert result.report_id == 2
    assert "실패" in result.title

    # 저장될 때 원본 텍스트가 들어갔는지 확인
    args, _ = mock_repo.save_weekly_report.call_args
    saved_data = args[3]
    assert saved_data["content"] == bad_response
