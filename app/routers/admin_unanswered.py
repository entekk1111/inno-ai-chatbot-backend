from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional
from app.models.admin import UnansweredUpdateRequest
from app.database import supabase

router = APIRouter(prefix="/api/admin/unanswered", tags=["Admin Unanswered"])


# 1. 미답변 질문 목록 조회
@router.get("")
def get_unanswered_queries(status: Optional[str] = Query(None)):
    try:
        query = supabase.table("unanswered_queries").select("*")
        if status:
            query = query.eq("status", status)
        res = query.order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        print(f"❌ [ADMIN GET ERROR]: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 2. 미답변 질문 수정 (Depends 제거)
@router.patch("/{id}")
def update_unanswered_query(id: str, body: UnansweredUpdateRequest, request: Request):
    try:
        auth_header = request.headers.get("authorization")
        if not auth_header:
            print("⚠️ [ADMIN PATCH] Authorization 헤더가 누락되었으나 임시로 수정을 허용합니다.")

        update_data = {k: v for k, v in body.dict().items() if v is not None}
        if not update_data:
            return {"ok": True}

        res = supabase.table("unanswered_queries").update(update_data).eq("id", id).execute()
        return {"ok": True, "data": res.data}
    except Exception as e:
        print(f"❌ [ADMIN PATCH ERROR]: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 3. 미답변 질문 삭제 (Depends 제거)
@router.delete("/{id}")
def delete_unanswered_query(id: str, request: Request):
    try:
        auth_header = request.headers.get("authorization")
        if not auth_header:
            print("⚠️ [ADMIN DELETE] Authorization 헤더가 누락되었으나 임시로 삭제를 허용합니다.")

        res = supabase.table("unanswered_queries").delete().eq("id", id).execute()
        return {"ok": True}
    except Exception as e:
        print(f"❌ [ADMIN DELETE ERROR]: {e}")
        raise HTTPException(status_code=500, detail=str(e))