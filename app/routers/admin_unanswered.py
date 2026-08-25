from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from app.models import UnansweredUpdateRequest
from app.security import get_current_user
from app.database import supabase
from app.models.admin import UnansweredUpdateRequest, UnansweredStatus

router = APIRouter(prefix="/api/admin/unanswered", tags=["Admin Unanswered"])

@router.get("")
def get_unanswered_queries(status: Optional[str] = Query(None)):
    query = supabase.table("unanswered_queries").select("*")
    if status:
        query = query.eq("status", status)
    res = query.order("created_at", desc=True).execute()
    return res.data

@router.patch("/{id}")
def update_unanswered_query(id: str, body: UnansweredUpdateRequest, current_user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    if not update_data:
        return {"ok": True}
    res = supabase.table("unanswered_queries").update(update_data).eq("id", id).execute()
    return {"ok": True}

@router.delete("/{id}")
def delete_unanswered_query(id: str, current_user: dict = Depends(get_current_user)):
    res = supabase.table("unanswered_queries").delete().eq("id", id).execute()
    return {"ok": True}