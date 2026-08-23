from fastapi import APIRouter, HTTPException
from app.models.chat import ChatRequest, ChatResponse
from app.services.rag_service import run_rag_pipeline
from app.database import supabase
import uuid

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        # 1. 세션 ID 검증 및 생성
        session_id = getattr(req, "session_id", None)
        
        if not session_id:
            session_id = str(uuid.uuid4())
            session_data = {
                "id": session_id,
                "title": req.message[:20] if req.message else "새 대화"
            }
            supabase.table("chat_sessions").insert(session_data).execute()

        # 2. RAG 파이프라인 실행
        allowed_groups = ["common", "admin"]
        rag_response = await run_rag_pipeline(req, allowed_groups)

        # 3. 유저 질문 & AI 답변 기록 저장 (role 필수 전달)
        try:
            messages_to_insert = [
                {
                    "session_id": session_id,
                    "role": "user",
                    "content": req.message
                },
                {
                    "session_id": session_id,
                    "role": "assistant",
                    "content": rag_response.answer
                }
            ]
            supabase.table("chat_messages").insert(messages_to_insert).execute()
            print(f"✅ [chat_messages 저장 성공] session_id: {session_id}")
        except Exception as msg_err:
            print(f"❌ [chat_messages 저장 실패]: {msg_err}")

        # 4. 세션 목록 최신화 (updated_at 갱신)
        try:
            supabase.table("chat_sessions").update({
                "updated_at": "now()"
            }).eq("id", session_id).execute()
        except Exception:
            pass

        # 프론트엔드로 session_id 전달
        rag_response.session_id = session_id
        return rag_response

    except Exception as e:
        print(f"❌ [Chat Endpoint Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))