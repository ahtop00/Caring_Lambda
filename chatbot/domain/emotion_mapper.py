# chatbot/domain/emotion_mapper.py
"""
Hume AI 53개 세부 감정 → 6대 분류 매핑 모듈

Hume Expression Measurement API가 반환하는 48개(prosody/burst) 또는 53개(language)
감정 score를 6대 분류(기쁨/슬픔/불안/분노/놀람/평온)로 매핑합니다.
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger()

# =============================================================================
# Hume 53개 감정 → 6대 분류 매핑 테이블
# =============================================================================
HUME_TO_CATEGORY = {
    # 기쁨 (happy) — 17개
    "Joy": "happy",
    "Amusement": "happy",
    "Excitement": "happy",
    "Contentment": "happy",
    "Ecstasy": "happy",
    "Satisfaction": "happy",
    "Triumph": "happy",
    "Pride": "happy",
    "Relief": "happy",
    "Admiration": "happy",
    "Adoration": "happy",
    "Aesthetic Appreciation": "happy",
    "Entrancement": "happy",
    "Love": "happy",
    "Romance": "happy",
    "Gratitude": "happy",      # language 전용
    "Enthusiasm": "happy",     # language 전용

    # 슬픔 (sad) — 8개
    "Sadness": "sad",
    "Disappointment": "sad",
    "Nostalgia": "sad",
    "Empathic Pain": "sad",
    "Shame": "sad",
    "Guilt": "sad",
    "Embarrassment": "sad",
    "Distress": "sad",

    # 불안 (anxiety) — 6개
    "Anxiety": "anxiety",
    "Fear": "anxiety",
    "Horror": "anxiety",
    "Doubt": "anxiety",
    "Awkwardness": "anxiety",
    "Confusion": "anxiety",

    # 분노 (angry) — 6개
    "Anger": "angry",
    "Contempt": "angry",
    "Disgust": "angry",
    "Annoyance": "angry",      # language 전용
    "Disapproval": "angry",    # language 전용
    "Envy": "angry",

    # 놀람 (surprise) — 5개
    "Surprise (positive)": "surprise",
    "Surprise (negative)": "surprise",
    "Awe": "surprise",
    "Realization": "surprise",
    "Interest": "surprise",

    # 평온 (neutral) — 6개
    "Calmness": "neutral",
    "Contemplation": "neutral",
    "Concentration": "neutral",
    "Determination": "neutral",
    "Boredom": "neutral",
    "Tiredness": "neutral",

    # 기타 (매핑되지 않는 감정은 무시)
    "Craving": "happy",
    "Desire": "happy",
    "Pain": "sad",
    "Sympathy": "sad",
    "Sarcasm": "angry",        # language 전용
}

# 6대 분류 영어 → 한국어 매핑
CATEGORY_KO = {
    "happy": "기쁨",
    "sad": "슬픔",
    "anxiety": "불안",
    "angry": "분노",
    "surprise": "놀람",
    "neutral": "평온",
}

# 모델별 가중치
MODEL_WEIGHTS = {
    "prosody": 0.4,
    "burst": 0.1,
    "language": 0.5,
}


@dataclass
class EmotionMapResult:
    """감정 매핑 결과"""
    primary_category: str       # 한국어 (기쁨/슬픔/불안/분노/놀람/평온)
    primary_category_en: str    # 영어 (happy/sad/anxiety/angry/surprise/neutral)
    secondary_category: str | None = None       # 한국어
    secondary_category_en: str | None = None    # 영어
    primary_emotions: list = field(default_factory=list)  # Hume 세부 감정 상위 3개
    sentiment_summary: float | None = None      # language sentiment weighted_mean
    emotion_trajectory: list = field(default_factory=list)  # utterance별 감정 변화
    confidence: float = 0.0    # primary 카테고리의 합산 score


def _aggregate_emotions_from_summary(summary: list) -> dict:
    """
    summary 배열 [{"name": "Sadness", "score": 0.8}, ...]을 6대 분류별로 합산합니다.
    Returns: {"happy": 0.5, "sad": 0.8, ...}
    """
    category_scores = {cat: 0.0 for cat in CATEGORY_KO}
    for item in summary:
        name = item.get("name", "")
        score = item.get("score", 0.0)
        category = HUME_TO_CATEGORY.get(name)
        if category:
            category_scores[category] += score
    return category_scores


def _extract_trajectory(emotion_analysis: dict) -> list:
    """
    prosody utterances에서 utterance별 주요 감정 변화를 추출합니다.
    Returns: [{"text": "...", "time": {...}, "primary_emotion": "sad", "top_emotions": [...]}, ...]
    """
    trajectory = []
    prosody = emotion_analysis.get("prosody") or {}
    utterances = prosody.get("utterances", [])

    for utt in utterances:
        top_emotions = utt.get("top_emotions", [])
        if not top_emotions:
            continue

        # 각 utterance의 top_emotions를 6대 분류로 매핑
        cat_scores = {}
        for emo in top_emotions:
            cat = HUME_TO_CATEGORY.get(emo.get("name", ""))
            if cat:
                cat_scores[cat] = cat_scores.get(cat, 0.0) + emo.get("score", 0.0)

        primary_cat = max(cat_scores, key=cat_scores.get) if cat_scores else "neutral"

        trajectory.append({
            "text": utt.get("text", ""),
            "time": utt.get("time", {}),
            "primary_emotion": CATEGORY_KO.get(primary_cat, "평온"),
            "primary_emotion_en": primary_cat,
            "top_emotions": top_emotions[:3],
        })

    return trajectory


def map_hume_emotions(emotion_analysis: dict) -> EmotionMapResult:
    """
    Hume AI emotion_analysis 데이터를 6대 분류로 매핑합니다.

    Args:
        emotion_analysis: Spring이 가공한 Hume 분석 결과
            {
                "source": "hume",
                "prosody": {"summary": [...], "utterances": [...]},
                "burst": {"summary": [...], "events": [...]},
                "language": {"summary": [...], "sentiment": {...}, "toxicity": [...], "utterances": [...]}
            }

    Returns:
        EmotionMapResult
    """
    if not emotion_analysis:
        return EmotionMapResult(
            primary_category="평온",
            primary_category_en="neutral",
            confidence=0.0,
        )

    # 1. 모델별 summary에서 6대 분류 합산
    weighted_scores = {cat: 0.0 for cat in CATEGORY_KO}
    total_weight = 0.0

    for model_name, weight in MODEL_WEIGHTS.items():
        model_data = emotion_analysis.get(model_name) or {}
        summary = model_data.get("summary", [])
        if not summary:
            continue

        cat_scores = _aggregate_emotions_from_summary(summary)
        for cat, score in cat_scores.items():
            weighted_scores[cat] += score * weight
        total_weight += weight

    # 가중치 정규화
    if total_weight > 0:
        for cat in weighted_scores:
            weighted_scores[cat] /= total_weight

    # 2. primary / secondary 도출
    sorted_cats = sorted(weighted_scores.items(), key=lambda x: x[1], reverse=True)
    primary_en = sorted_cats[0][0] if sorted_cats else "neutral"
    primary_score = sorted_cats[0][1] if sorted_cats else 0.0

    secondary_en = None
    if len(sorted_cats) >= 2:
        second_score = sorted_cats[1][1]
        # primary와 score 차이 0.2 이내일 때만 secondary 부여
        if primary_score - second_score <= 0.2 and second_score > 0.05:
            secondary_en = sorted_cats[1][0]

    # 3. 상위 세부 감정 추출 (모든 summary 통합)
    all_emotions = {}
    for model_name in ["prosody", "language"]:
        model_data = emotion_analysis.get(model_name) or {}
        for item in model_data.get("summary", []):
            name = item.get("name", "")
            score = item.get("score", 0.0)
            if name in all_emotions:
                all_emotions[name] = max(all_emotions[name], score)
            else:
                all_emotions[name] = score

    top_detail_emotions = sorted(
        [{"name": k, "score": v} for k, v in all_emotions.items()],
        key=lambda x: x["score"],
        reverse=True
    )[:3]

    # 4. sentiment 추출
    language_data = emotion_analysis.get("language") or {}
    sentiment_data = language_data.get("sentiment") or {}
    sentiment_summary = sentiment_data.get("weighted_mean")

    # 5. 감정 궤적 추출
    trajectory = _extract_trajectory(emotion_analysis)

    return EmotionMapResult(
        primary_category=CATEGORY_KO.get(primary_en, "평온"),
        primary_category_en=primary_en,
        secondary_category=CATEGORY_KO.get(secondary_en) if secondary_en else None,
        secondary_category_en=secondary_en,
        primary_emotions=top_detail_emotions,
        sentiment_summary=sentiment_summary,
        emotion_trajectory=trajectory,
        confidence=primary_score,
    )
