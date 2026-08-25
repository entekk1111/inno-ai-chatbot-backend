from pydantic import BaseModel
from typing import Optional, Literal

JobType = Literal["pm_pl", "developer"]

class UserCreate(BaseModel):
    user_id: str
    password: str
    name: str
    dept: Optional[str] = None
    position: Optional[str] = None  # ★ position 필드 추가
    job: Optional[JobType] = None
    role: Optional[str] = "user"

class UserUpdate(BaseModel):
    name: Optional[str] = None
    dept: Optional[str] = None
    position: Optional[str] = None  # ★ position 필드 추가
    job: Optional[JobType] = None
    role: Optional[str] = None
    password: Optional[str] = None