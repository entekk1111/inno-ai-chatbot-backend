from pydantic import BaseModel
from typing import Optional, Literal

DeptType = Literal["service", "tech_support"]
PositionType = Literal[
    "사원", "선임", "책임", "수석보", "수석",
    "이사", "상무", "전무", "부사장", "사장", "대표"
]
UnansweredStatus = Literal["open", "in_progress", "resolved"]

# 사용자 생성 요청
class UserCreateRequest(BaseModel):
    name: str
    user_id: str
    password: str
    dept: DeptType
    position: PositionType
    role: Optional[str] = "user"

# [추가] 사용자 수정 요청
class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    dept: Optional[DeptType] = None
    position: Optional[PositionType] = None
    role: Optional[str] = None

# 미답변 질문 수정 요청
class UnansweredUpdateRequest(BaseModel):
    status: Optional[UnansweredStatus] = None
    note: Optional[str] = None