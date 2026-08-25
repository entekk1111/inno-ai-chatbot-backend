import os
import re
from datetime import datetime
from typing import List
from app.database import supabase
from app.models.chat import ChatRequest, ChatResponse, SourceDocument

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

api_key = os.getenv("OPENAI_API_KEY")

llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0.2,
    openai_api_key=api_key
)

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=api_key,
    chunk_size=1000,
    request_timeout=60
)

def is_toc_text(text: str) -> bool:
    if len(re.findall(r'\.{5,}', text)) >= 3:
        return True
    return False

async def run_rag_pipeline(req: ChatRequest, allowed_groups: List[str]) -> ChatResponse:
    user_query = req.message
    today_str = datetime.now().strftime("%Y-%m-%d")

    print("\n==================== [RAG DEBUG START] ====================")
    print(f"1. [입력 질문]: '{user_query}'")
    print(f"2. [허용 그룹(allowed_groups)]: {allowed_groups}")

    # 1. 권한 검증 및 valid_doc_ids 확보
    res = supabase.table("chat_documents") \
        .select("id, file_name, access_group, expires_at") \
        .eq("is_deleted", False) \
        .execute()

    print(f"3. [chat_documents 테이블 조회 결과 건수]: {len(res.data) if res.data else 0}")

    if not res.data:
        print("❌ [실패] chat_documents에 등록된 문서가 없음")
        print("==================== [RAG DEBUG END] ====================\n")
        return ChatResponse(answer="등록된 문서가 없습니다.", reply="등록된 문서가 없습니다.", sources=[])

    scope_obj = getattr(req, "scope", None) or {}
    if hasattr(scope_obj, "dict"):
        scope_obj = scope_obj.dict()
    
    scope_mode = scope_obj.get("mode", "all")
    selected_doc_ids = [str(i).lower() for i in scope_obj.get("document_ids", [])]

    print(f"4. [Scope 옵션]: mode='{scope_mode}', selected_doc_ids={selected_doc_ids}")

    valid_doc_ids = set()
    doc_name_map = {}
    for doc in res.data:
        doc_id_raw = doc["id"]
        doc_id = str(doc_id_raw).lower()
        acc_grp = doc.get("access_group")
        group_ok = acc_grp in allowed_groups if allowed_groups else True
        expires_at = doc.get("expires_at")
        time_ok = not expires_at or expires_at >= today_str

        if group_ok and time_ok:
            if scope_mode == "selected" and selected_doc_ids:
                if doc_id in selected_doc_ids:
                    valid_doc_ids.add(doc_id)
                    doc_name_map[doc_id] = doc.get("file_name", "문서")
            else:
                valid_doc_ids.add(doc_id)
                doc_name_map[doc_id] = doc.get("file_name", "문서")
        else:
            print(f"   - [열람 제외 문서]: id={doc_id}, group={acc_grp} (group_ok={group_ok}, time_ok={time_ok})")

    print(f"5. [최종 권한 통과 valid_doc_ids 목록 ({len(valid_doc_ids)}개)]: {list(valid_doc_ids)}")

    if not valid_doc_ids:
        print("❌ [실패] valid_doc_ids가 비어있음 (권한 또는 만료일자 원인)")
        print("==================== [RAG DEBUG END] ====================\n")
        return ChatResponse(answer="열람 권한이 있는 문서가 없습니다.", reply="열람 권한이 있는 문서가 없습니다.", sources=[])

    # 2. Vector DB 직접 RPC 호출 (DB 레벨 필터링)
    query_vector = embeddings.embed_query(user_query)
    
    # Supabase RPC 호출
    rpc_res = supabase.rpc(
        "match_documents",
        {
            "query_embedding": query_vector,
            "match_count": 30,
            "filter_doc_ids": list(valid_doc_ids)  # 👈 DB 검색 시 valid_doc_ids만 조회하도록 전달
        }
    ).execute()

    raw_docs = []
    if rpc_res.data:
        for item in rpc_res.data:
            metadata = item.get("metadata") or {}
            raw_docs.append(Document(page_content=item.get("content", ""), metadata=metadata))

    print(f"6. [Vector Store에서 가져온 Raw 청크 수]: {len(raw_docs)}개")

    if len(raw_docs) > 0:
        print(f"   - [첫번째 Raw 청크 메타데이터 샘플]: {raw_docs[0].metadata}")
        print(f"   - [첫번째 Raw 청크 본문 샘플 (50자)]: {raw_docs[0].page_content[:50]}...")

    retrieved_docs = []
    for idx, d in enumerate(raw_docs):
        raw_meta_id = d.metadata.get("doc_id") or d.metadata.get("document_id") or d.metadata.get("id")
        meta_doc_id = str(raw_meta_id).lower() if raw_meta_id is not None else ""
        
        if is_toc_text(d.page_content):
            print(f"   - [{idx}번 청크] 목차 정규식에 걸려 제외됨")
            continue

        if not meta_doc_id or meta_doc_id in valid_doc_ids:
            retrieved_docs.append(d)
        else:
            print(f"   - [{idx}번 청크] ID 미매칭으로 제외: 청크의 doc_id='{meta_doc_id}' ∉ valid_doc_ids")

    final_docs = retrieved_docs[:10]
    print(f"7. [최종 필터링 통과 후 Context에 들어가는 청크 수]: {len(final_docs)}개")
    print("==================== [RAG DEBUG END] ====================\n")

    if not final_docs:
        msg = "공유된 문서에서 관련된 내용을 찾을 수 없습니다."
        return ChatResponse(answer=msg, reply=msg, sources=[])

    # 3. Context 구성
    context_chunks = []
    for d in final_docs:
        raw_meta_id = d.metadata.get("doc_id") or d.metadata.get("document_id") or d.metadata.get("id")
        doc_id = str(raw_meta_id).lower() if raw_meta_id is not None else ""
        
        file_name = (
            d.metadata.get('source_name') 
            or d.metadata.get('source') 
            or doc_name_map.get(doc_id) 
            or '문서'
        )
        if "/" in str(file_name) or "\\" in str(file_name):
            file_name = os.path.basename(str(file_name))

        raw_page = d.metadata.get('page') if d.metadata.get('page') is not None else d.metadata.get('page_number')
        page_num = int(raw_page) + 1 if raw_page is not None and str(raw_page).isdigit() else '미상'

        context_chunks.append(f"[출처: {file_name} / 페이지: {page_num}]\n{d.page_content}")

    context_text = "\n\n---\n\n".join(context_chunks)

    # 4. 프롬프트 실행
    system_instruction = (
        "당신은 사내 지식 베이스 검색 전문 AI입니다. 아래 [참고 문서]에 포함된 텍스트, 표, 구문, 기호, 예시 등을 바탕으로 사용자의 질문에 상세히 답변하세요.\n\n"
        "[답변 작성 지침]\n"
        "1. 문서에 언급된 개념, 문법 규칙, 사용 기호, 데이터 타입, 함수 및 예시가 있다면 이를 직접 인용하여 구체적이고 전문적으로 설명하세요.\n"
        "2. 절대로 '몇 페이지를 참고하세요'라는 식으로 페이지 번호만 안내하지 마세요. 문서 본문에 적힌 실제 가이드 내용과 개념을 풀어서 설명해야 합니다.\n"
        "3. 질문과 관련된 본문 내용이 존재한다면 풍부한 정보와 맥락을 포함하여 친절하게 답변하세요.\n\n"
        "제공된 문서(Context)에서 질문에 대한 답을 찾을 수 없거나 내용이 부족한 경우, 반드시 답변 첫 줄에 [UNANSWERED] 키워드를 포함하여 응답하세요.\n\n"
        f"[참고 문서 Context]:\n{context_text}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_message}"),
        ("human", "{input}"),
    ])

    chain = prompt | llm
    response = await chain.ainvoke({
        "system_message": system_instruction,
        "input": user_query
    })

    reply_text = str(response.content)

    # 5. 출처 매핑
    sources_list = []
    seen_content = set()

    for doc in final_docs:
        raw_meta_id = doc.metadata.get("doc_id") or doc.metadata.get("document_id") or doc.metadata.get("id")
        doc_id = str(raw_meta_id).lower() if raw_meta_id is not None else "unknown"
        
        source_name = (
            doc.metadata.get("source_name") 
            or doc.metadata.get("source") 
            or doc_name_map.get(doc_id) 
            or "문서"
        )
        if "/" in str(source_name) or "\\" in str(source_name):
            source_name = os.path.basename(str(source_name))

        raw_page = doc.metadata.get('page') if doc.metadata.get('page') is not None else doc.metadata.get('page_number')
        parsed_page = int(raw_page) + 1 if raw_page is not None and str(raw_page).isdigit() else None

        content_snippet = doc.page_content.strip()
        if content_snippet not in seen_content:
            seen_content.add(content_snippet)
            sources_list.append(
                SourceDocument(
                    id=doc_id,
                    file_name=str(source_name),
                    content=content_snippet,
                    page=parsed_page
                )
            )

    return ChatResponse(
        answer=reply_text,
        reply=reply_text,
        sources=sources_list
    )