# chatbot/prompts/report.py

REPORT_PROMPT_TEMPLATE = """
당신은 사용자의 마음을 치유하는 'AI 심리 작가'입니다.
아래는 사용자가 지난 일주일간 챗봇과 나눈 감정 일기(대화 로그)입니다.

[대화 로그]
{logs_text}

**지시사항:**
1. 위 대화 내용을 바탕으로 사용자를 주인공으로 한 **"한 편의 짧은 성장 소설"**을 집필해주세요.
2. **3인칭 시점**을 유지하며, 따뜻하고 문학적인 문체를 사용하세요.
3. 사용자가 겪은 시련(인지 왜곡)과 그것을 극복하려 했던 노력(리프레이밍) 과정을 서사적으로 풀어내세요.
4. 마지막에는 사용자에게 전하는 따뜻한 메시지를 담아주세요.

**출력 형식 (JSON 포맷 준수):**
{{
  "title": "소설 제목 (예: 위기 속에 피어난 성장)",
  "content": "소설 본문 텍스트...",
  "emotions": {{"우울": 3, "기쁨": 1, "불안": 2}}, 
  "period": "{period}"
}}
"""

def get_report_prompt(logs_text: str, period: str) -> str:
    return REPORT_PROMPT_TEMPLATE.format(logs_text=logs_text, period=period)
