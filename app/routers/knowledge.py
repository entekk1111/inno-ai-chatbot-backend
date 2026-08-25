from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.database import supabase
from app.routers.documents import get_allowed_groups  # documents.py의 권한 함수 재활용

router = APIRouter(prefix="/api", tags=["Knowledge Base"])

@router.get("/knowledge-base")
async def get_knowledge_base(user_id: Optional[str] = Query(None)):
    try:
        # 1. 사용자 권한 그룹 계산
        allowed_groups = get_allowed_groups(user_id)

        # 2. 권한에 맞는 문서만 조회
        res = supabase.table("chat_documents") \
            .select("*") \
            .in_("access_group", allowed_groups) \
            .eq("is_deleted", False) \
            .order("created_at", desc=True) \
            .execute()

        documents = res.data or []

        return {
            "document_count": len(documents),
            "documents": documents,
            "allowed_groups": allowed_groups,
            "last_indexed_at": "정상 작동 중"
        }
    except Exception as e:
        print(f"❌ [Knowledge Base 조회 오류]: {e}")
        return {
            "document_count": 0,
            "documents": [],
            "last_indexed_at": "정보 없음"
        }