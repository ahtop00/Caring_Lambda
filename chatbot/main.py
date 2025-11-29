# chatbot/main.py
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError

from controller import chat_controller, search_controller, report_controller, dev_controller

from exception import (
    AppError,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler
)

tags_metadata = [
    {"name": "Welfare Search", "description": "복지/구인 정보 검색"},
    {"name": "CBT Reframing", "description": "심리 상담 및 리프레이밍"},
    {"name": "Report", "description": "주간 리포트 생성"},
    {"name": "Health Check", "description": "상태 확인"},
]

app = FastAPI(
    title="SAPORI Chatbot API",
    description="SAPORI 챗봇 서비스 백엔드 API",
    version="0.4.0",
    contact={
        "name": "SAPORI Dev Team",
        "email": "ehcl1027@gmail.com",
    },
    openapi_tags=tags_metadata,
    openapi_prefix="/prod",
    docs_url="/chatbot/docs",
    openapi_url="/chatbot/openapi.json"
)

# --- 전역 예외 핸들러 등록 ---
app.add_exception_handler(AppError, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)
# ----------------------------------

app.include_router(search_controller.router)
app.include_router(chat_controller.router)
app.include_router(report_controller.router)
app.include_router(dev_controller.router)

@app.get("/chatbot/health", tags=["Health Check"])
def health_check():
    return {"status": "ok"}
