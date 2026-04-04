# chatbot/domain/text_emotion_analyzer.py
"""
텍스트 자체 감정 분석 모듈

Hume AI를 거치지 않는 텍스트 전용 입력에서
Vertex AI(Gemini)를 사용하여 6대 감정 분류를 수행합니다.
"""
import logging
from domain.emotion_mapper import EmotionMapResult, CATEGORY_KO
from util.json_parser import parse_llm_json

logger = logging.getLogger()

TEXT_EMOTION_ANALYSIS_PROMPT = """
다음 텍스트의 감정을 분석해주세요. 6가지 감정 카테고리에 대한 점수를 매겨주세요.

[텍스트]
"{text}"

**분석 기준:**
- happy (기쁨): 긍정적 감정, 만족, 즐거움, 감사
- sad (슬픔): 상실, 실망, 후회, 수치심
- anxiety (불안): 걱정, 두려움, 혼란, 불확실
- angry (분노): 화남, 짜증, 경멸, 질투
- surprise (놀람): 예상 밖 상황, 놀라움, 깨달음
- neutral (평온): 차분함, 무감정, 피로, 집중

**주의사항:**
- 'neutral'은 정말로 감정이 없는 사무적인 내용일 때만 높은 점수를 주세요
- 부정적 상황을 담담하게 서술해도 sad 또는 anxiety로 판단하세요
- "괜찮아요", "별거 아니에요" 같은 방어기제가 보이면 neutral이 아닌 실제 감정을 추론하세요

**출력 형식 (JSON):**
{{
    "primary": "가장 강한 감정 카테고리 (happy/sad/anxiety/angry/surprise/neutral)",
    "secondary": "두 번째 감정 카테고리 또는 null",
    "confidence": 0.0~1.0,
    "scores": {{
        "happy": 0.0~1.0,
        "sad": 0.0~1.0,
        "anxiety": 0.0~1.0,
        "angry": 0.0~1.0,
        "surprise": 0.0~1.0,
        "neutral": 0.0~1.0
    }}
}}
"""


def analyze_text_emotion(text: str, llm_service) -> EmotionMapResult:
    """
    텍스트에서 감정을 자체 분석합니다 (Hume 없이).

    Args:
        text: 사용자 입력 텍스트
        llm_service: LLMService 인스턴스

    Returns:
        EmotionMapResult
    """
    try:
        prompt = TEXT_EMOTION_ANALYSIS_PROMPT.format(text=text)
        raw_response = llm_service.get_llm_response(prompt, use_bedrock=False)
        result = parse_llm_json(raw_response)

        primary_en = result.get("primary", "neutral")
        secondary_en = result.get("secondary")
        confidence = result.get("confidence", 0.5)

        # secondary가 primary와 같거나 빈 문자열이면 None
        if secondary_en == primary_en or not secondary_en:
            secondary_en = None

        # 유효한 카테고리인지 검증
        if primary_en not in CATEGORY_KO:
            primary_en = "neutral"
        if secondary_en and secondary_en not in CATEGORY_KO:
            secondary_en = None

        return EmotionMapResult(
            primary_category=CATEGORY_KO.get(primary_en, "평온"),
            primary_category_en=primary_en,
            secondary_category=CATEGORY_KO.get(secondary_en) if secondary_en else None,
            secondary_category_en=secondary_en,
            primary_emotions=[],  # 텍스트 자체 분석에는 Hume 세부 감정 없음
            sentiment_summary=None,
            emotion_trajectory=[],
            confidence=confidence,
        )

    except Exception as e:
        logger.warning(f"텍스트 감정 자체 분석 실패, neutral로 폴백: {e}")
        return EmotionMapResult(
            primary_category="평온",
            primary_category_en="neutral",
            confidence=0.0,
        )
