from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from app.database import supabase
from app.models.document import PermissionUpdateRequest
from app.services.document_service import process_and_save_document

router = APIRouter(prefix="/api/documents", tags=["Documents"])

# 1. 문서 목록 조회
@router.get("")
async def get_documents():
    """RDB에서 삭제되지 않은 문서 목록 조회"""
    res = supabase.table("chat_documents") \
        .select("*") \
        .eq("is_deleted", False) \
        .order("created_at", desc=True) \
        .execute()
    return res.data

# 2. 지식 베이스 목록 조회 (동적 경로 /{document_id} 보다 항상 위에 선언해야 함!)
@router.get("/knowledge-base")
async def get_knowledge_base():
    """지식 베이스 문서 목록 조회 (/api/documents/knowledge-base)"""
    res = supabase.table("chat_documents") \
        .select("*") \
        .eq("is_deleted", False) \
        .execute()
    return res.data

# 3. 문서 업로드
@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    access_group: str = Form("common"),
    expires_at: Optional[str] = Form(None)
):
    doc_id = await process_and_save_document(file, access_group, expires_at)
    return {"ok": True, "document_id": doc_id, "message": "문서 업로드 완료"}

# 4. 권한 수정 (동적 경로)
@router.patch("/{document_id}")
async def update_document_permission(document_id: str, req: PermissionUpdateRequest):
    update_data = {"access_group": req.access_group}
    if req.expires_at is not None:
        update_data["expires_at"] = req.expires_at if req.expires_at != "" else None

    supabase.table("chat_documents").update(update_data).eq("id", document_id).execute()
    return {"ok": True, "message": "권한 변경 성공"}

# 5. 문서 삭제 (동적 경로)
@router.delete("/{document_id}")
async def delete_document(document_id: str):
    # 소프트 삭제
    supabase.table("chat_documents").update({"is_deleted": True}).eq("id", document_id).execute()
    return {"ok": True, "message": "문서 삭제 성공"}