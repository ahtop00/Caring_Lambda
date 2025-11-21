from pydantic import BaseModel, Field

# --- 요청(Request) ---
class ReframingRequest(BaseModel):
    user_input: str = Field(..., description="리프레이밍할 사용자 문장")

# --- 응답(Response) ---
class ReframingResponse(BaseModel):
    empathy: str
    reframed_thought: str
