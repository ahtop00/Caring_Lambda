# chatbot/test/services/test_emotion_mapper.py
import pytest
from domain.emotion_mapper import (
    map_hume_emotions,
    HUME_TO_CATEGORY,
    CATEGORY_KO,
    EmotionMapResult,
)


class TestHumeToCategory:
    """Hume 감정 → 6대 분류 매핑 테이블 검증"""

    def test_all_48_prosody_emotions_mapped(self):
        """Prosody/Burst 48개 감정이 모두 매핑되어 있는지 확인"""
        prosody_emotions = [
            "Admiration", "Adoration", "Aesthetic Appreciation", "Amusement",
            "Anger", "Anxiety", "Awe", "Awkwardness", "Boredom", "Calmness",
            "Concentration", "Contemplation", "Confusion", "Contempt",
            "Contentment", "Craving", "Desire", "Determination",
            "Disappointment", "Disgust", "Distress", "Doubt", "Ecstasy",
            "Embarrassment", "Empathic Pain", "Entrancement", "Envy",
            "Excitement", "Fear", "Guilt", "Horror", "Interest", "Joy",
            "Love", "Nostalgia", "Pain", "Pride", "Realization", "Relief",
            "Romance", "Sadness", "Satisfaction", "Shame",
            "Surprise (negative)", "Surprise (positive)", "Sympathy",
            "Tiredness", "Triumph"
        ]
        for emotion in prosody_emotions:
            assert emotion in HUME_TO_CATEGORY, f"'{emotion}' 매핑 누락"

    def test_language_extra_5_emotions_mapped(self):
        """Language 전용 추가 5개 감정이 매핑되어 있는지 확인"""
        language_extras = ["Annoyance", "Disapproval", "Enthusiasm", "Gratitude", "Sarcasm"]
        for emotion in language_extras:
            assert emotion in HUME_TO_CATEGORY, f"Language 전용 '{emotion}' 매핑 누락"

    def test_all_6_categories_present(self):
        """6대 분류 모두 최소 1개 이상의 감정이 매핑되어 있는지 확인"""
        categories_used = set(HUME_TO_CATEGORY.values())
        for cat in CATEGORY_KO:
            assert cat in categories_used, f"'{cat}' 카테고리에 매핑된 감정 없음"


class TestMapHumeEmotions:
    """map_hume_emotions 함수 테스트"""

    def test_empty_input_returns_neutral(self):
        """빈 입력은 평온/neutral 반환"""
        result = map_hume_emotions({})
        assert result.primary_category == "평온"
        assert result.primary_category_en == "neutral"

    def test_none_input_returns_neutral(self):
        """None 입력은 평온/neutral 반환"""
        result = map_hume_emotions(None)
        assert result.primary_category == "평온"
        assert result.primary_category_en == "neutral"

    def test_sadness_dominant(self):
        """슬픔이 지배적인 경우"""
        emotion_analysis = {
            "source": "hume",
            "prosody": {
                "summary": [
                    {"name": "Sadness", "score": 0.8},
                    {"name": "Distress", "score": 0.6},
                ],
                "utterances": []
            },
            "language": {
                "summary": [
                    {"name": "Sadness", "score": 0.7},
                    {"name": "Disappointment", "score": 0.5},
                ],
                "utterances": []
            }
        }
        result = map_hume_emotions(emotion_analysis)
        assert result.primary_category == "슬픔"
        assert result.primary_category_en == "sad"

    def test_complex_emotion_primary_secondary(self):
        """복합 감정 (primary + secondary) 도출"""
        emotion_analysis = {
            "source": "hume",
            "prosody": {
                "summary": [
                    {"name": "Joy", "score": 0.7},
                    {"name": "Sadness", "score": 0.6},
                ],
                "utterances": []
            },
            "language": {
                "summary": [
                    {"name": "Joy", "score": 0.65},
                    {"name": "Sadness", "score": 0.55},
                ],
                "utterances": []
            }
        }
        result = map_hume_emotions(emotion_analysis)
        assert result.primary_category == "기쁨"
        assert result.secondary_category == "슬픔"

    def test_no_secondary_when_gap_large(self):
        """primary와 secondary 차이가 0.2 초과면 secondary=None"""
        emotion_analysis = {
            "source": "hume",
            "prosody": {
                "summary": [
                    {"name": "Anger", "score": 0.9},
                    {"name": "Joy", "score": 0.1},
                ],
                "utterances": []
            },
            "language": {
                "summary": [
                    {"name": "Anger", "score": 0.85},
                ],
                "utterances": []
            }
        }
        result = map_hume_emotions(emotion_analysis)
        assert result.primary_category == "분노"
        assert result.secondary_category is None

    def test_trajectory_extraction(self):
        """감정 궤적(trajectory) 추출"""
        emotion_analysis = {
            "source": "hume",
            "prosody": {
                "summary": [],
                "utterances": [
                    {
                        "text": "힘들었어",
                        "time": {"begin": 0.0, "end": 1.5},
                        "confidence": 0.9,
                        "top_emotions": [
                            {"name": "Sadness", "score": 0.8},
                            {"name": "Anxiety", "score": 0.5},
                        ]
                    },
                    {
                        "text": "그래도 괜찮아",
                        "time": {"begin": 1.5, "end": 3.0},
                        "confidence": 0.85,
                        "top_emotions": [
                            {"name": "Joy", "score": 0.6},
                            {"name": "Relief", "score": 0.4},
                        ]
                    }
                ]
            }
        }
        result = map_hume_emotions(emotion_analysis)
        assert len(result.emotion_trajectory) == 2
        assert result.emotion_trajectory[0]["primary_emotion"] == "슬픔"
        assert result.emotion_trajectory[1]["primary_emotion"] == "기쁨"

    def test_sentiment_extraction(self):
        """sentiment 데이터 추출"""
        emotion_analysis = {
            "source": "hume",
            "language": {
                "summary": [{"name": "Sadness", "score": 0.5}],
                "sentiment": {
                    "distribution": [],
                    "dominant": 3,
                    "weighted_mean": 3.5
                },
                "utterances": []
            }
        }
        result = map_hume_emotions(emotion_analysis)
        assert result.sentiment_summary == 3.5
