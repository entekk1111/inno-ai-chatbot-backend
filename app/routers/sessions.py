from fastapi import APIRouter, HTTPException, status
from app.database import supabase

router = APIRouter(prefix="/api", tags=["Sessions"])

# 1. 세션 목록 조회 API
@router.get("/sessions")
async def get_sessions():
    try:
        response = supabase.table("chat_sessions") \
            .select("id, title, updated_at") \
            .order("updated_at", desc=True) \
            .execute()
        
        sessions = [
            {
                "session_id": item["id"],
                "title": item["title"],
                "updated_at": item["updated_at"]
            }
            for item in response.data
        ]
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 2. 특정 세션 메시지 기록 조회 API
@router.get("/sessions/{session_id}")
async def get_session_history(session_id: str):
    try:
        response = supabase.table("chat_messages") \
            .select("role, content, created_at") \
            .eq("session_id", session_id) \
            .order("created_at", desc=False) \
            .execute()
            
        return {"messages": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. 단일 세션 삭제 API
@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def delete_session(session_id: str):
    try:
        supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        supabase.table("chat_sessions").delete().eq("id", session_id).execute()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. 전체 세션 삭제 API
@router.delete("/sessions", status_code=status.HTTP_200_OK)
async def delete_all_sessions():
    try:
        supabase.table("chat_messages").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        supabase.table("chat_sessions").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        return {"ok": True, "message": "모든 세션이 삭제되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))