from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any
from app.database import supabase
from app.security import get_current_user  # 👈 JWT 토큰에서 user_id를 자동 추출하는 의존성

router = APIRouter(prefix="/api", tags=["Sessions"])


# 1. 세션 목록 조회 API
@router.get("/sessions")
async def get_sessions(current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user.get("user_id")

        response = supabase.table("chat_sessions") \
            .select("id, title, updated_at") \
            .eq("user_id", user_id) \
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
async def get_session_history(
    session_id: str, 
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        user_id = current_user.get("user_id")

        # 1) 세션 존재 여부 및 소유자 확인
        session_res = supabase.table("chat_sessions") \
            .select("user_id") \
            .eq("id", session_id) \
            .execute()

        if not session_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="존재하지 않는 세션입니다."
            )

        owner_id = session_res.data[0].get("user_id")

        # 2) 본인 세션이 아니면 403 Forbidden 차단
        if owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 세션에 대한 접근 권한이 없습니다."
            )

        # 3) 메시지 기록 조회
        response = supabase.table("chat_messages") \
            .select("role, content, created_at") \
            .eq("session_id", session_id) \
            .order("created_at", desc=False) \
            .execute()
            
        return {"messages": response.data}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 3. 단일 세션 삭제 API
@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def delete_session(
    session_id: str, 
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        user_id = current_user.get("user_id")

        # 1) 세션 소유자 확인
        session_res = supabase.table("chat_sessions") \
            .select("user_id") \
            .eq("id", session_id) \
            .execute()

        if not session_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="존재하지 않는 세션입니다."
            )

        owner_id = session_res.data[0].get("user_id")

        # 2) 본인 세션이 아니면 403 Forbidden 차단
        if owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 세션을 삭제할 권한이 없습니다."
            )

        # 3) 삭제 수행
        supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        supabase.table("chat_sessions").delete().eq("id", session_id).execute()
        return {"ok": True}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 4. 특정 사용자의 전체 세션 삭제 API
@router.delete("/sessions", status_code=status.HTTP_200_OK)
async def delete_all_sessions(current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = current_user.get("user_id")

        # 1) 해당 사용자의 세션 ID 목록 추출
        user_sessions_res = supabase.table("chat_sessions") \
            .select("id") \
            .eq("user_id", user_id) \
            .execute()
        
        session_ids = [s["id"] for s in user_sessions_res.data]

        if session_ids:
            # 2) 해당 세션들에 속한 메시지 및 세션 삭제
            supabase.table("chat_messages").delete().in_("session_id", session_ids).execute()
            supabase.table("chat_sessions").delete().eq("user_id", user_id).execute()

        return {"ok": True, "message": "사용자의 모든 세션이 삭제되었습니다."}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))