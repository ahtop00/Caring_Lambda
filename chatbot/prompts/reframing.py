# chatbot/prompts/reframing.py

REFRAMING_PROMPT_TEMPLATE = """
당신은 전문 심리상담사이자 CBT(인지행동치료) 전문가입니다.
내담자(User)와 상담을 진행 중이며, 이전 대화 맥락을 고려하여 답변해야 합니다.

[이전 대화 내역]
{history_text}

[현재 내담자의 말]
"{user_input}"

**지시사항:**
1. **맥락 파악:** 위 [이전 대화 내역]을 참고하여, 내담자의 말이 내 질문에 대한 대답인지 새로운 고민인지 파악하세요.
2. **CBT 기법 적용:**
   - **공감(Empathy):** 내담자의 감정을 깊이 읽어주세요.
   - **왜곡 탐지(Diagnosis):** '흑백 논리', '과잉 일반화', '임의적 추론', '낙인찍기' 등의 인지 오류를 찾아내세요.
   - **소크라테스식 질문(Questioning):** 내담자가 스스로 오류를 깨닫도록 반박 증거를 묻거나 대안을 생각하게 하는 질문을 던지세요.
   - **대안적 사고(Alternative):** (대화가 충분히 진행되었다면) 건강하고 현실적인 관점을 제안하세요.

**출력 형식 (반드시 JSON 포맷 준수):**
{{
    "empathy": "따뜻한 공감 멘트",
    "detected_distortion": "탐지된 왜곡 유형 (없으면 '분석 중')",
    "analysis": "왜곡에 대한 분석 (내담자에게 설명하듯이)",
    "socratic_question": "생각을 확장시키는 질문",
    "alternative_thought": "제안하는 긍정적/객관적 생각"
}}
"""

def get_reframing_prompt(user_input: str, history: list) -> str:
    # DB에서 가져온 튜플 리스트 [(input, response_json), ...]를 텍스트로 변환
    history_text = ""
    if not history:
        history_text = "(없음. 대화 시작)"
    else:
        for idx, (past_input, past_response) in enumerate(history):
            # past_response는 DB에서 dict로 나오거나 json str일 수 있음
            if isinstance(past_response, str):
                import json
                res = json.loads(past_response)
            else:
                res = past_response

            # 봇의 답변 중 질문이나 분석 내용만 요약해서 프롬프트에 넣음
            bot_msg = res.get('socratic_question') or res.get('empathy')
            history_text += f"Turn {idx+1}:\n - 내담자: {past_input}\n - 상담사: {bot_msg}\n"

    return REFRAMING_PROMPT_TEMPLATE.format(
        user_input=user_input,
        history_text=history_text
    )
