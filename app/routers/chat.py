from fastapi import APIRouter, HTTPException
from app.models.chat import ChatRequest, ChatResponse
from app.services.rag_service import run_rag_pipeline
from app.database import supabase
from app.routers.documents import get_allowed_groups  # 💡 문서 권한 함수 재사용
import uuid

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        session_id = getattr(req, "session_id", None)
        user_id = getattr(req, "user_id", None)
        
        # 💡 documents.py와 동일한 검증된 권한 로직 적용
        allowed_groups = get_allowed_groups(user_id)
        print(f"💬 [Chat 요청] user_id: '{user_id}' | 허용 권한 그룹: {allowed_groups}")

        # RAG 파이프라인 동적으로 동기화된 allowed_groups 전달
        rag_response = await run_rag_pipeline(req, allowed_groups)

        # 2-1. 미답변 질문 판별 및 태그 제거
        answer_text = getattr(rag_response, "answer", "") or ""
        sources = getattr(rag_response, "sources", [])

        # [UNANSWERED] 태그 존재 여부 또는 sources 비어있는지 확인
        is_unanswered = ("[UNANSWERED]" in answer_text) or (len(sources) == 0)

        # [UNANSWERED] 태그 제거 및 정제
        cleaned_answer = answer_text.replace("[UNANSWERED]", "").lstrip(" :").strip()

        # 미답변인 경우 엉뚱하게 조회된 sources 목록 초기화
        if is_unanswered:
            sources = []
            rag_response.sources = []

        # ★ [핵심] answer뿐만 아니라 reply 필드도 정제된 텍스트로 업데이트
        rag_response.answer = cleaned_answer
        if hasattr(rag_response, "reply"):
            rag_response.reply = cleaned_answer

        rag_response.unanswered = is_unanswered 

        # 3. 미답변 질문 DB 저장
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

        # 4. 메시지 저장 (태그가 제거된 cleaned_answer 적용)
        messages_to_insert = [
            {"session_id": session_id, "role": "user", "content": req.message},
            {"session_id": session_id, "role": "assistant", "content": cleaned_answer}
        ]
        supabase.table("chat_messages").insert(messages_to_insert).execute()

        # 5. 세션 updated_at 갱신
        if session_id:
            supabase.table("chat_sessions").update({
                "updated_at": "now()"
            }).eq("id", session_id).execute()

        rag_response.session_id = session_id
        return rag_response

    except Exception as e:
        print(f"❌ [Chat Endpoint Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))