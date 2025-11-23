from fastapi import FastAPI
from controller import chat_controller, search_controller, report_controller

tags_metadata = [
    {
        "name": "Welfare Search",
        "description": "RAG(검색 증강 생성)를 활용한 **복지 정책 및 구인 정보 검색** API입니다.",
    },
    {
        "name": "CBT Reframing",
        "description": "CBT(인지행동치료) 기반 **심리 상담 및 리프레이밍** API입니다. (SQS 비동기 로그 저장 포함)",
    },
    {
        "name": "Health Check",
        "description": "서버 및 로드밸런서 상태 확인용 API입니다.",
    },
]

app = FastAPI(
    title="SAPORI Chatbot API",
    description="""
    # SAPORI 챗봇 서비스 백엔드 API

    이 API는 **사회적 약자를 위한 복지 정보 제공** 및 **멘탈 헬스케어(CBT)** 기능을 제공합니다.
    
    ## 🚀 주요 기능
    * **🔍 복지/구인 검색**: 사용자의 상황(나이, 장애 여부 등)에 맞는 맞춤형 혜택 검색
    * **🧠 CBT 리프레이밍**: 사용자의 부정적 사고를 분석하고, 건강한 관점으로 전환 유도
    * **📊 심리 분석**: 대화 로그를 분석하여 사용자의 핵심 신념(Core Belief) 파악 (데이터 적재)
    """,
    version="0.3.1",
    contact={
        "name": "SAPORI Dev Team",
        "email": "ehcl1027@gmail.com",
    },
    openapi_tags=tags_metadata,
    openapi_prefix="/prod",
    docs_url="/chatbot/docs",
    openapi_url="/chatbot/openapi.json"
)

app.include_router(search_controller.router)
app.include_router(chat_controller.router)
app.include_router(report_controller.router)

@app.get("/chatbot/health", tags=["Health Check"], summary="서버 상태 확인")
def health_check():
    return {"status": "ok"}
