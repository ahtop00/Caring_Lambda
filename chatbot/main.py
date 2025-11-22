# chatbot/main.py
from fastapi import FastAPI
from schema import SearchRequest, SearchResponse, ReframingRequest, ReframingResponse
from domain.search_logic import execute_search
from domain.reframing_logic import execute_reframing

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
    version="1.1.0",
    contact={
        "name": "SAPORI Dev Team",
        "email": "ehcl1027@gmail.com",
    },
    openapi_tags=tags_metadata,
    openapi_prefix="/prod",
    docs_url="/chatbot/docs",
    openapi_url="/chatbot/openapi.json"
)

@app.post(
    "/chatbot/query",
    response_model=SearchResponse,
    tags=["Welfare Search"],
    summary="복지/구인 정보 검색",
    description="사용자의 질문과 개인 정보(선택)를 입력받아, 관련된 복지 정책이나 채용 공고를 검색하고 답변을 생성합니다."
)
def search_endpoint(request: SearchRequest):
    return execute_search(
        user_chat=request.query2,
        user_info=request.query1,
        use_bedrock=request.bedrock
    )

@app.post(
    "/chatbot/reframing",
    response_model=ReframingResponse,
    tags=["CBT Reframing"],
    summary="CBT 리프레이밍 상담",
    description="""
    사용자의 고민을 입력받아 CBT 기반의 상담을 제공합니다.
    
    **[처리 과정]**
    1. **공감**: 감정 파악 및 위로
    2. **왜곡 탐지**: 인지적 오류(흑백논리 등) 분석
    3. **질문/대안**: 소크라테스식 질문 제공
    4. **로그 저장**: 분석용 데이터 SQS 비동기 전송

    ---
    ### 📝 Swagger 테스트 가이드 (필독)
    대화의 **맥락(Context)을 유지**하며 테스트하려면 아래 규칙을 지켜주세요.

    1. **`session_id` (필수)**: 
       - **랜덤한 6자리 영문+숫자** 조합으로 직접 입력해주세요. (예: `A1B2C3`, `KD83SA`)
       - 이 ID가 같아야 **'하나의 대화 스레드'**로 인식되어 이전 대화 기억을 불러옵니다.
    
    2. **`user_id` (필수)**:
       - 테스트하는 동안 **동일한 ID**를 사용하세요. (예: `test_user_1`)
       - `user_id`와 `session_id`가 모두 일치해야 이전 턴의 대화 내용을 기억합니다.
    
    3. **새로운 상담 시작**:
       - 대화 주제를 바꾸고 싶다면 `session_id`를 새로운 값(예: `NEW001`)으로 변경해서 요청하세요.
    """
)
def reframing_endpoint(request: ReframingRequest):
    return execute_reframing(request)

@app.get(
    "/chatbot/health",
    tags=["Health Check"],
    summary="서버 상태 확인 (Health Check)",
    description="API 서버가 정상적으로 작동 중인지 확인합니다. (200 OK 반환)"
)
def health_check():
    return {"status": "ok"}
