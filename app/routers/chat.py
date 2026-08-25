from fastapi import APIRouter, HTTPException, Query
from app.models.chat import ChatRequest, ChatResponse
from app.services.rag_service import run_rag_pipeline
from app.database import supabase
from app.routers.documents import get_allowed_groups
from typing import Optional
import uuid

router = APIRouter(prefix="/api", tags=["chat"])

# ---------------------------------------------------------
# 1. 채팅 세션 목록 조회 API (GET /api/sessions)
# ---------------------------------------------------------
@router.get("/sessions")
async def get_sessions(user_id: Optional[str] = Query(None)):
    if not user_id:
        return []

    try:
        res = supabase.table("chat_sessions") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("updated_at", desc=True) \
            .execute()

        return res.data or []
    except Exception as e:
        print(f"❌ [get_sessions 오류]: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# 2. 채팅 메인 메시지 처리 API (POST /api/chat)
# ---------------------------------------------------------
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        session_id = getattr(req, "session_id", None)
        user_id = getattr(req, "user_id", None)

        # [수정 1] session_id가 없으면 신규 UUID 자동 발급
        if not session_id:
            session_id = str(uuid.uuid4())

        # [수정 2] DB 세션 존재 여부 확인 및 자동 생성/갱신
        if user_id:
            try:
                session_check = supabase.table("chat_sessions").select("id").eq("id", session_id).execute()
                if not session_check.data:
                    # 세션이 존재하지 않으면 신규 생성 (첫 질문을 title로 설정)
                    first_title = req.message[:30] if req.message else "새 대화"
                    supabase.table("chat_sessions").insert({
                        "id": session_id,
                        "user_id": user_id,
                        "title": first_title,
                        "created_at": "now()",
                        "updated_at": "now()"
                    }).execute()
                    print(f"✅ [새 세션 생성 완료]: {session_id}")
                else:
                    # 기존 세션은 updated_at 시간만 갱신
                    supabase.table("chat_sessions").update({
                        "updated_at": "now()"
                    }).eq("id", session_id).execute()
            except Exception as sess_err:
                print(f"⚠️ [chat_sessions 처리 실패]: {sess_err}")

        # 3. 유저 권한 조회 및 RAG 실행
        allowed_groups = get_allowed_groups(user_id)
        print(f"💬 [Chat 요청] user_id: '{user_id}' | 허용 권한 그룹: {allowed_groups}")

        rag_response = await run_rag_pipeline(req, allowed_groups)

        # 4. 답변 정제 및 미답변 여부 체크
        answer_text = getattr(rag_response, "answer", "") or ""
        sources = getattr(rag_response, "sources", [])

        is_unanswered = ("[UNANSWERED]" in answer_text) or (len(sources) == 0)
        cleaned_answer = answer_text.replace("[UNANSWERED]", "").lstrip(" :").strip()

        if is_unanswered:
            sources = []
            rag_response.sources = []

        rag_response.answer = cleaned_answer
        if hasattr(rag_response, "reply"):
            rag_response.reply = cleaned_answer

        rag_response.unanswered = is_unanswered

        # 5. 미답변 질문 저장
        if is_unanswered:
            try:
                unanswered_data = {
                    "question": req.message,
                    "user_id": user_id,
                    "session_id": session_id,
                    "status": "open",
                    "note": ""
                }
                supabase.table("unanswered_queries").insert(unanswered_data).execute()
                print(f"✅ [미답변 질문 DB 저장 성공]: {req.message}")
            except Exception as unans_err:
                print(f"❌ [미답변 질문 DB 저장 실패]: {unans_err}")

        # 6. 대화 히스토리 저장 (발급된/확정된 session_id 저장)
        messages_to_insert = [
            {"session_id": session_id, "role": "user", "content": req.message},
            {"session_id": session_id, "role": "assistant", "content": cleaned_answer}
        ]
        supabase.table("chat_messages").insert(messages_to_insert).execute()

        # 7. 응답 객체에 session_id 동기화 후 반환
        rag_response.session_id = session_id
        return rag_response

    except Exception as e:
        print(f"❌ [Chat Endpoint Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        