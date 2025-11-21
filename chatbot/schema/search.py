from pydantic import BaseModel, Field
from typing import List, Optional

# --- 요청(Request) ---
class SearchRequest(BaseModel):
    query1: str = Field(default="제공된 정보 없음", description="사용자 정보 (선택)")
    query2: str = Field(..., description="사용자 질문 (필수)")
    bedrock: bool = Field(default=False, description="Bedrock 사용 여부")

# --- 응답(Response) ---
class ServiceItem(BaseModel):
    service_name: str
    summary: str
    target: Optional[str] = None
    region: str
    url: str

class SearchResponse(BaseModel):
    answer: str
    services: List[ServiceItem]
