# chatbot/prompts/mind_diary.py
from prompts.emotion_strategies import get_emotion_strategy_block

MIND_DIARY_PROMPT_TEMPLATE = """
당신은 전문 심리상담사이자 CBT(인지행동치료) 전문가 '도란이'입니다.
사용자 '{user_name}'님이 작성한 '마음일기'를 읽고, 먼저 다가가서 대화를 시작해야 합니다.

[마음일기 정보]
- 주제(질문): {question}
- 작성 내용: "{content}"
- 작성 일시: {recorded_at}

[감정 분석 결과]
{emotion_desc}
{emotion_strategy}
[분석 기준: 인지 오류 및 긍정 상태]
1. 흑백사고: 완전한 실패 아니면 대단한 성공, 양극단으로만 구분함.
2. 선택적 추상: 부정적인 세부 사항에만 초점을 맞추고 긍정적인 전체 맥락을 무시함.
3. 자의적 추론: 충분한 증거 없이 부정적인 결론을 내림.
4. 과잉일반화: 한두 번의 사건으로 일반적인 결론을 내림.
5. 확대 및 축소: 단점은 과대평가하고 장점은 과소평가함.
6. 개인화: 자신과 무관한 일을 자신의 탓으로 돌림.
7. 정서적 추론: 객관적 사실보다 자신의 부정적 느낌을 사실로 믿음.
8. 긍정 격하: 긍정적인 경험이나 성취를 운이나 우연으로 치부하며 무시함.
9. 파국화: 사건을 지나치게 과장하여 최악의 상황을 두려워함.
10. 잘못된 별칭 붙이기: 자신에게 부정적인 꼬리표(별칭)를 붙임.
11. 긍정 정서 강화: 인지 오류가 없고, 기분이 좋거나 긍정적인/희망찬 내용일 경우.

**지시사항:**
1. **복합 감정 읽기:** 단순히 주된 감정만 언급하지 말고, 세부 수치에서 **두드러지는 다른 감정**이 있다면 함께 읽어주세요. (예: "슬픔과 함께 약간의 불안도 느껴지네요.")
2. **공감(Empathy):** 사용자의 이름을 부르며, 작성된 내용과 감정에 대해 따뜻하게 공감하는 첫인사를 건네세요.
3. **왜곡 탐지(Distortion):** - 일기 내용에서 위 [분석 기준]의 1~10번에 해당하는 오류가 보이면 해당 명칭을 기입하세요.
   - **긍정적이거나 희망찬 내용이라면 '긍정 정서 강화'라고 기입하세요.**
   - 별다른 특징이 없다면 '없음'으로 표기하세요.
4. **분석(Analysis):** 사용자가 왜 그런 감정을 느꼈을지, 심리적 배경을 부드럽게 분석해주세요.
5. **질문(Question):** - 인지 오류가 있다면 스스로 생각해보게 하는 질문을 던지세요.
   - **'긍정 정서 강화' 상태라면 그 기분을 더 생생하게 느낄 수 있는 질문**을 해주세요.
6. **대안적 사고(Alternative):** - 상황을 긍정적/객관적으로 볼 수 있는 힘이 되는 말을 해주세요.
   - 이미 긍정적이라면 그 마음을 지지하고 응원해주세요.

**출력 형식 (반드시 JSON 포맷 준수):**
{{
    "empathy": "따뜻한 공감 및 첫인사",
    "detected_distortion": "탐지된 항목 (예: '긍정 정서 강화', '흑백사고' 등. 없으면 '없음')",
    "analysis": "일기 내용에 대한 심리적 분석",
    "socratic_question": "대화를 이어가는 열린 질문",
    "alternative_thought": "힘이 되는 긍정적인 관점 제안"
}}
"""


def _build_emotion_desc(emotion_map_result, legacy_emotion: dict) -> tuple[str, str]:
    """
    감정 분석 결과를 프롬프트용 문자열로 변환한다.

    Returns:
        (emotion_desc, primary_en) — primary_en은 strategy block 선택에 사용
    """
    if emotion_map_result:
        primary = emotion_map_result.primary_category
        primary_en = emotion_map_result.primary_category_en
        secondary_en = emotion_map_result.secondary_category_en
        confidence = emotion_map_result.confidence

        desc = (
            f"- 주된 감정: **{primary}** (강도: {confidence:.2f})\n"
        )

        if emotion_map_result.secondary_category:
            desc += f"- 복합 감정: **{emotion_map_result.secondary_category}**도 함께 감지됨\n"

        # 세부 감정 top3
        if emotion_map_result.primary_emotions:
            details = ", ".join(
                f"{e['name']}({e['score']:.3f})"
                for e in emotion_map_result.primary_emotions
            )
            desc += f"- 주요 세부 감정: {details}\n"

        # 언어 감성 극성
        if emotion_map_result.sentiment_summary is not None:
            val = emotion_map_result.sentiment_summary
            label = "부정적" if val < 4 else "긍정적" if val > 6 else "중립적"
            desc += f"- 언어 감성 극성: {val:.1f}/9.0 ({label})\n"

        # 발화별 감정 궤적
        if emotion_map_result.emotion_trajectory:
            desc += "\n[발화 흐름]\n"
            for i, traj in enumerate(emotion_map_result.emotion_trajectory):
                text = traj.get("text", "")
                emo = traj.get("primary_emotion", "")
                top = traj.get("top_emotions", [])
                top_str = ", ".join(
                    f"{e['name']}({e['score']:.2f})" for e in top[:2]
                )
                desc += f"  구간 {i + 1}: \"{text}\" → {emo} ({top_str})\n"

        return desc, primary_en, secondary_en

    else:
        # 기존 방식 (하위 호환)
        top_emotion = legacy_emotion.get('top_emotion', 'neutral')
        details = legacy_emotion.get('details', {})
        desc = f"- 주된 감정: {top_emotion}\n"
        for emo, score in details.items():
            if score > 0:
                desc += f"  - {emo}: {int(score * 100)}%\n"
        return desc, top_emotion, None


def get_mind_diary_prompt(
        user_name: str,
        question: str,
        content: str,
        recorded_at: str,
        emotion_map_result=None,
        legacy_emotion: dict = None,
) -> str:
    """
    마음일기 프롬프트 생성.

    Args:
        user_name: 사용자 이름
        question: 마음일기 질문
        content: STT 변환 텍스트 (없으면 빈 문자열)
        recorded_at: 기록 일시
        emotion_map_result: EmotionMapResult (Hume 매핑 결과)
        legacy_emotion: 기존 방식 감정 dict (하위 호환용)
    """
    content_display = content if content else "(음성으로 기록됨 — 텍스트 변환 없음)"

    emotion_desc, primary_en, secondary_en = _build_emotion_desc(
        emotion_map_result, legacy_emotion or {}
    )

    strategy = get_emotion_strategy_block(primary_en, secondary_en)

    return MIND_DIARY_PROMPT_TEMPLATE.format(
        user_name=user_name,
        question=question,
        content=content_display,
        recorded_at=recorded_at,
        emotion_desc=emotion_desc,
        emotion_strategy=strategy,
    )
