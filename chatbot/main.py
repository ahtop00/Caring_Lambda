# chatbot/main.py
from fastapi import FastAPI
from schema import SearchRequest, SearchResponse, ReframingRequest, ReframingResponse
from domain.search_logic import execute_search
from domain.reframing_logic import execute_reframing

app = FastAPI(
    title="Welfare Chatbot API",
    description="복지/구인 정보 검색 및 리프레이밍 챗봇 API",
    version="1.0.0",
    openapi_prefix="/prod",
    docs_url="/chatbot/docs",
    openapi_url="/chatbot/openapi.json"
)

@app.post("/chatbot/query", response_model=SearchResponse)
def search_endpoint(request: SearchRequest):
    return execute_search(
        user_chat=request.query2,
        user_info=request.query1,
        use_bedrock=request.bedrock
    )

@app.post("/chatbot/reframing", response_model=ReframingResponse)
def reframing_endpoint(request: ReframingRequest):
    return execute_reframing(request.user_input)

@app.get("/chatbot/health")
def health_check():
    return {"status": "ok"}
