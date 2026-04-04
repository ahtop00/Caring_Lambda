# chatbot/test/services/test_emotion_strategies.py
import pytest
from prompts.emotion_strategies import get_emotion_strategy_block, EMOTION_STRATEGY_BLOCKS


class TestGetEmotionStrategyBlock:
    """감정별 전략 블록 리졸버 함수 테스트"""

    @pytest.mark.parametrize("emotion", ["happy", "sad", "neutral", "angry", "anxiety", "surprise"])
    def test_known_emotions_return_non_empty(self, emotion):
        """6개 정규 감정 모두 비어있지 않은 블록을 반환해야 한다"""
        result = get_emotion_strategy_block(emotion)
        assert len(result) > 0, f"'{emotion}' 전략 블록이 비어있음"
        assert "감정 맞춤 전략" in result

    def test_none_returns_empty(self):
        """None 입력 시 빈 문자열 반환 (기존 동작 유지)"""
        assert get_emotion_strategy_block(None) == ""

    def test_empty_string_returns_empty(self):
        """빈 문자열 입력 시 빈 문자열 반환"""
        assert get_emotion_strategy_block("") == ""

    def test_unknown_emotion_returns_empty(self):
        """알 수 없는 감정명은 빈 문자열 반환 (안전한 fallback)"""
        assert get_emotion_strategy_block("unknown_emotion") == ""

    def test_alias_sadness_maps_to_sad(self):
        """'sadness' → 'sad' 매핑 확인 (마음일기 시스템 호환)"""
        result = get_emotion_strategy_block("sadness")
        assert result == get_emotion_strategy_block("sad")
        assert len(result) > 0

    def test_alias_anger_maps_to_angry(self):
        """'anger' → 'angry' 매핑 확인"""
        result = get_emotion_strategy_block("anger")
        assert result == get_emotion_strategy_block("angry")
        assert len(result) > 0

    def test_alias_fear_maps_to_anxiety(self):
        """'fear' → 'anxiety' 매핑 확인"""
        result = get_emotion_strategy_block("fear")
        assert result == get_emotion_strategy_block("anxiety")

    def test_case_insensitive(self):
        """대소문자 구분 없이 동작해야 한다"""
        assert get_emotion_strategy_block("SAD") == get_emotion_strategy_block("sad")
        assert get_emotion_strategy_block("Anxiety") == get_emotion_strategy_block("anxiety")
        assert get_emotion_strategy_block("HAPPY") == get_emotion_strategy_block("happy")

    def test_whitespace_handling(self):
        """앞뒤 공백이 있어도 정상 동작"""
        assert get_emotion_strategy_block("  sad  ") == get_emotion_strategy_block("sad")
        assert get_emotion_strategy_block(" anxiety ") == get_emotion_strategy_block("anxiety")

    def test_all_blocks_have_three_sections(self):
        """모든 전략 블록이 3단 구조(치료적 태도/우선 기법/금기)를 포함하는지 확인"""
        for emotion, block in EMOTION_STRATEGY_BLOCKS.items():
            assert "치료적 태도" in block, f"'{emotion}' 블록에 '치료적 태도' 섹션 누락"
            assert "우선 기법" in block, f"'{emotion}' 블록에 '우선 기법' 섹션 누락"
            assert "금기" in block, f"'{emotion}' 블록에 '금기' 섹션 누락"

    def test_secondary_emotion_adds_complex_block(self):
        """secondary emotion이 있으면 복합 감정 전략 블록이 추가되어야 한다"""
        result = get_emotion_strategy_block("happy", secondary_emotion="sad")
        assert "감정 맞춤 전략" in result
        assert "복합 감정 안내" in result
        assert "happy + sad" in result

    def test_secondary_same_as_primary_no_complex(self):
        """secondary가 primary와 동일하면 복합 블록이 추가되지 않아야 한다"""
        result = get_emotion_strategy_block("sad", secondary_emotion="sad")
        assert "복합 감정 안내" not in result

    def test_secondary_none_no_complex(self):
        """secondary가 None이면 기존 동작과 동일"""
        result = get_emotion_strategy_block("angry", secondary_emotion=None)
        assert "복합 감정 안내" not in result
        assert "감정 맞춤 전략" in result
