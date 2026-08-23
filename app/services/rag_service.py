import os
import re
from datetime import datetime
from typing import List
from app.database import supabase
from app.models.chat import ChatRequest, ChatResponse, SourceDocument

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import SupabaseVectorStore
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

vectorstore = SupabaseVectorStore(
    client=supabase,
    embedding=embeddings,
    table_name="documents",
    query_name="match_documents"
)

def is_toc_text(text: str) -> bool:
    """검색 결과에서 목차용 노이즈 청크 여부 2차 검증"""
    if len(re.findall(r'(\.{3,}|\.\s\.\s\.)', text)) >= 2:
        return True
    return False

async def run_rag_pipeline(req: ChatRequest, allowed_groups: List[str]) -> ChatResponse:
    user_query = req.message
    today_str = datetime.now().strftime("%Y-%m-%d")

    # 1. 권한 검증 및 valid_doc_ids 확보
    res = supabase.table("chat_documents") \
        .select("id, file_name, access_group, expires_at") \
        .eq("is_deleted", False) \
        .execute()

    if not res.data:
        return ChatResponse(answer="등록된 문서가 없습니다.", reply="등록된 문서가 없습니다.", sources=[])

    valid_doc_ids = []
    doc_name_map = {}
    for doc in res.data:
        group_ok = doc.get("access_group") in allowed_groups if allowed_groups else True
        expires_at = doc.get("expires_at")
        time_ok = not expires_at or expires_at >= today_str

        if group_ok and time_ok:
            doc_id = str(doc["id"])
            valid_doc_ids.append(doc_id)
            doc_name_map[doc_id] = doc.get("file_name", "문서")

    if not valid_doc_ids:
        return ChatResponse(answer="열람 권한이 있는 문서가 없습니다.", reply="열람 권한이 있는 문서가 없습니다.", sources=[])

    # 2. k=25로 넉넉하게 가져온 뒤 목차 2차 제거 & 메모리 필터링
    raw_docs = vectorstore.similarity_search(user_query, k=25)
    
    retrieved_docs = []
    for d in raw_docs:
        meta_doc_id = str(d.metadata.get("doc_id", ""))
        
        # 2차 목차 필터링
        if is_toc_text(d.page_content):
            continue

        if not meta_doc_id or meta_doc_id in valid_doc_ids:
            retrieved_docs.append(d)

    # 본문 청크 상위 10개 추출
    final_docs = retrieved_docs[:10]

    if not final_docs:
        msg = "공유된 문서에서 관련된 내용을 찾을 수 없습니다."
        return ChatResponse(answer=msg, reply=msg, sources=[])

    # 3. Context 구성
    context_chunks = []
    for d in final_docs:
        doc_id = str(d.metadata.get('doc_id', ''))
        
        file_name = (
            d.metadata.get('source_name') 
            or d.metadata.get('source') 
            or doc_name_map.get(doc_id) 
            or '문서'
        )
        if "/" in file_name or "\\" in file_name:
            file_name = os.path.basename(file_name)

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
        doc_id = str(doc.metadata.get("doc_id", "unknown"))
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