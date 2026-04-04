# chatbot/test/services/test_reframing_service.py
import pytest
import json
from unittest.mock import Mock, patch
from schema.reframing import ReframingRequest, VoiceReframingRequest, EmotionAnalysis, HumeProsody, HumeLanguage, HumeBurst, EmotionScore
from domain.reframing_logic import ReframingService
from repository.chat_repository import ChatRepository
from service.llm_service import LLMService


def test_execute_reframing_success():
    """
    [Scenario] 텍스트 상담: LLM 응답 처리 및 동기 DB 저장(임베딩 포함) 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    mock_llm_service.get_embedding.return_value = [0.1] * 1024

    mock_chat_repo.get_chat_history.return_value = []
    mock_chat_repo.get_session_turn_count.return_value = 1

    llm_output = {
        "empathy": "많이 힘드셨군요.",
        "detected_distortion": "흑백논리",
        "analysis": "분석 내용...",
        "socratic_question": "질문?",
        "alternative_thought": "대안",
        "top_emotion": "anxiety"
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(llm_output)

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    request = ReframingRequest(user_id="user1", session_id="sess1", user_input="난 망했어")
    result = service.execute_reframing(request)

    # 응답 필드 변환 확인 (top_emotion -> emotion)
    assert result["emotion"] == "anxiety"
    assert result["empathy"] == "많이 힘드셨군요."

    mock_chat_repo.get_chat_history.assert_called_once()
    # LLM은 2번 호출됨 (자체 감정 분석 1회 + 상담 응답 1회)
    assert mock_llm_service.get_llm_response.call_count >= 1

    # 동기 저장 검증
    mock_llm_service.get_embedding.assert_called_once_with("난 망했어")
    mock_chat_repo.log_cbt_session.assert_called_once()


def test_execute_reframing_llm_failure():
    """
    [Scenario] LLM 응답 실패(Fallback) 시에도 DB 저장이 수행되는지 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    mock_llm_service.get_embedding.return_value = [0.0] * 1024

    mock_chat_repo.get_chat_history.return_value = []
    mock_chat_repo.get_session_turn_count.return_value = 1
    mock_llm_service.get_llm_response.return_value = "JSON 아님 Error"

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    request = ReframingRequest(user_id="user1", session_id="sess1", user_input="테스트")
    result = service.execute_reframing(request)

    assert result["detected_distortion"] == "분석 불가"
    assert result.get("emotion") == "neutral"

    mock_chat_repo.log_cbt_session.assert_called_once()


def test_execute_voice_reframing_with_legacy_emotion():
    """
    [Scenario] 음성 상담 (기존 emotion dict 방식): 하위 호환 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    mock_llm_service.get_embedding.return_value = [0.1] * 1024

    mock_chat_repo.get_chat_history.return_value = []
    mock_chat_repo.get_session_turn_count.return_value = 1

    llm_output = {
        "empathy": "목소리에서 슬픔이 느껴지네요.",
        "detected_distortion": "없음",
        "analysis": "분석...",
        "socratic_question": "질문?",
        "alternative_thought": "대안"
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(llm_output)

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    voice_request = VoiceReframingRequest(
        user_id="user_voice",
        session_id="sess_voice",
        user_input="너무 슬퍼요",
        emotion={"top_emotion": "sad", "confidence": 0.95},
        s3_url="https://s3.bucket/file.mp3"
    )

    result = service.execute_voice_reframing(voice_request)

    assert result["empathy"] == "목소리에서 슬픔이 느껴지네요."
    assert result["emotion"] == "sad"

    mock_chat_repo.log_cbt_session.assert_called_once()
    _, kwargs = mock_chat_repo.log_cbt_session.call_args
    assert kwargs["s3_url"] == "https://s3.bucket/file.mp3"


def test_execute_voice_reframing_with_hume_emotion_analysis():
    """
    [Scenario] 음성 상담 (Hume AI): emotion_analysis를 사용하여 감정 매핑 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    mock_llm_service.get_embedding.return_value = [0.1] * 1024
    mock_chat_repo.get_chat_history.return_value = []
    mock_chat_repo.get_session_turn_count.return_value = 1

    llm_output = {
        "empathy": "많이 힘드셨군요.",
        "detected_distortion": "흑백사고",
        "analysis": "분석...",
        "socratic_question": "질문?",
        "alternative_thought": "대안"
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(llm_output)

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    # Hume 분석 결과로 요청
    emotion_analysis = EmotionAnalysis(
        source="hume",
        prosody=HumeProsody(
            summary=[
                EmotionScore(name="Sadness", score=0.821),
                EmotionScore(name="Anxiety", score=0.714),
            ],
            utterances=[]
        ),
        burst=HumeBurst(summary=[], events=[]),
        language=HumeLanguage(
            summary=[
                EmotionScore(name="Sadness", score=0.793),
                EmotionScore(name="Anxiety", score=0.612),
            ],
            utterances=[]
        )
    )

    voice_request = VoiceReframingRequest(
        user_id="user_hume",
        session_id="sess_hume",
        user_input="오늘 너무 힘들었어",
        emotion_analysis=emotion_analysis,
        s3_url="https://s3.bucket/audio.wav"
    )

    result = service.execute_voice_reframing(voice_request)

    # Hume 매핑 결과 확인
    assert result["emotion"] == "sad"
    assert "emotion_result" in result
    assert result["emotion_result"]["primary_category"] == "슬픔"

    # 프롬프트에 Hume 데이터가 포함되었는지 확인
    actual_prompt = mock_llm_service.get_llm_response.call_args[0][0]
    assert "슬픔" in actual_prompt or "Sadness" in actual_prompt

    mock_chat_repo.log_cbt_session.assert_called_once()


def test_execute_voice_reframing_hume_with_secondary_emotion():
    """
    [Scenario] Hume AI 복합 감정 (primary + secondary) 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    mock_llm_service.get_embedding.return_value = [0.1] * 1024
    mock_chat_repo.get_chat_history.return_value = []
    mock_chat_repo.get_session_turn_count.return_value = 1

    llm_output = {
        "empathy": "기쁘면서도 슬픈 마음이시군요.",
        "detected_distortion": "긍정 정서 강화",
        "analysis": "분석...",
        "socratic_question": "질문?",
        "alternative_thought": "대안"
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(llm_output)

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    # 기쁨과 슬픔이 동시에 높은 경우
    emotion_analysis = EmotionAnalysis(
        source="hume",
        prosody=HumeProsody(
            summary=[
                EmotionScore(name="Joy", score=0.65),
                EmotionScore(name="Sadness", score=0.55),
            ],
            utterances=[]
        ),
        language=HumeLanguage(
            summary=[
                EmotionScore(name="Joy", score=0.70),
                EmotionScore(name="Sadness", score=0.60),
            ],
            utterances=[]
        )
    )

    voice_request = VoiceReframingRequest(
        user_id="user_complex",
        session_id="sess_complex",
        user_input="칭찬받았는데 외롭다",
        emotion_analysis=emotion_analysis,
    )

    result = service.execute_voice_reframing(voice_request)

    assert "emotion_result" in result
    emotion_result = result["emotion_result"]
    # primary는 기쁨 (happy)
    assert emotion_result["primary_category"] == "기쁨"
    # secondary는 슬픔 (score 차이 0.2 이내)
    assert emotion_result["secondary_category"] == "슬픔"


def test_execute_reframing_with_emotion_strategy():
    """
    [Scenario] 텍스트 상담 + 감정 전략 블록 주입 테스트
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)
    mock_llm_service.get_embedding.return_value = [0.1] * 1024
    mock_chat_repo.get_chat_history.return_value = []
    mock_chat_repo.get_session_turn_count.return_value = 1

    llm_output = {
        "empathy": "많이 불안하셨군요.",
        "detected_distortion": "파국화",
        "analysis": "분석...",
        "socratic_question": "질문?",
        "alternative_thought": "대안",
        "top_emotion": "anxiety"
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(llm_output)

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    request = ReframingRequest(
        user_id="user1", session_id="sess1",
        user_input="시험이 너무 걱정돼요",
        emotion="anxiety"
    )
    result = service.execute_reframing(request)

    # LLM에 전달된 프롬프트에 전략 블록이 포함되었는지 검증
    # 마지막 LLM 호출이 상담 프롬프트 (첫 번째는 감정 분석일 수 있음)
    calls = mock_llm_service.get_llm_response.call_args_list
    # emotion 힌트가 있으면 자체 감정 분석 스킵 → 1회 호출
    actual_prompt = calls[-1][0][0]
    assert "감정 맞춤 전략" in actual_prompt
    assert "불안" in actual_prompt


def test_execute_voice_reframing_hume_null_fallback():
    """
    [Scenario] Hume 실패 시 emotion_analysis=None → 기본 상담 수행
    """
    mock_chat_repo = Mock(spec=ChatRepository)
    mock_llm_service = Mock(spec=LLMService)

    mock_llm_service.get_embedding.return_value = [0.1] * 1024
    mock_chat_repo.get_chat_history.return_value = []
    mock_chat_repo.get_session_turn_count.return_value = 1

    llm_output = {
        "empathy": "어떤 마음이신지 궁금하네요.",
        "detected_distortion": "없음",
        "analysis": "분석...",
        "socratic_question": "질문?",
        "alternative_thought": "대안",
        "top_emotion": "neutral"
    }
    mock_llm_service.get_llm_response.return_value = json.dumps(llm_output)

    service = ReframingService(chat_repo=mock_chat_repo, llm_service=mock_llm_service)

    # emotion_analysis도 없고 emotion도 없는 경우
    voice_request = VoiceReframingRequest(
        user_id="user_fallback",
        session_id="sess_fallback",
        user_input="그냥 좀 그래요",
    )

    result = service.execute_voice_reframing(voice_request)

    assert result["emotion"] == "neutral"
    mock_chat_repo.log_cbt_session.assert_called_once()
