from pydantic import BaseModel
from typing import Optional

class DocumentResponse(BaseModel):
    id: str
    file_name: str
    access_group: str
    expires_at: Optional[str] = None
    created_at: str

class PermissionUpdateRequest(BaseModel):
    access_group: str
    expires_at: Optional[str] = None