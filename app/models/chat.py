from pydantic import BaseModel
from typing import List, Optional

class SourceDocument(BaseModel):
    id: str
    file_name: str
    content: Optional[str] = ""  # 💡 참고문서 보기에 표시할 매칭 텍스트/스니펫
    page: Optional[int] = None   # 💡 페이지 번호

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = "admin"

class ChatResponse(BaseModel):
    answer: str
    reply: str
    sources: List[SourceDocument] = []
    session_id: Optional[str] = None