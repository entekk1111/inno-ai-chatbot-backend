from fastapi import APIRouter, HTTPException
from app.database import supabase

router = APIRouter(prefix="/api", tags=["Knowledge Base"])

@router.get("/knowledge-base")
async def get_knowledge_base():
    try:
        # 삭제되지 않은 문서 개수 조회
        res = supabase.table("chat_documents") \
            .select("id", count="exact") \
            .eq("is_deleted", False) \
            .execute()
        
        count = res.count if res.count is not None else len(res.data)
        
        return {
            "document_count": count,
            "last_indexed_at": "정상 작동 중"
        }
    except Exception as e:
        # 테이블이 다르거나 오류 발생 시 기본값 반환
        return {
            "document_count": 0,
            "last_indexed_at": "정보 없음"
        }