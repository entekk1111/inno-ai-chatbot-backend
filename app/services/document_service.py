import os
import re
import uuid
from typing import List, Optional, Any
from fastapi import UploadFile

from app.database import supabase
from app.config import UPLOAD_DIR, OPENAI_API_KEY

from langchain_community.document_loaders import PyMuPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=OPENAI_API_KEY,
    chunk_size=1000,
    request_timeout=60
)

vectorstore = SupabaseVectorStore(
    client=supabase,
    embedding=embeddings,
    table_name="documents",
    query_name="match_documents"
)

def is_table_of_contents_chunk(text: str) -> bool:
    """목차(Table of Contents) 성격의 청크인지 정밀 검사"""
    # 1. 연속된 점(........)이나 점-공백 패턴이 3개 이상 들어간 경우
    dot_pattern_count = len(re.findall(r'(\.{3,}|\.\s\.\s\.)', text))
    if dot_pattern_count >= 2:
        return True

    # 2. 줄 끝에 페이지 번호 숫자가 반복해서 나열되는 전형적인 목차 형태
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return False
        
    toc_line_count = 0
    for line in lines:
        # 문장 끝이 숫자로 끝나면서 길이가 짧거나 목차 형태인 경우
        if re.search(r'\.{2,}\s*\d+$', line) or re.search(r'\s{3,}\d+$', line):
            toc_line_count += 1

    if len(lines) > 0 and (toc_line_count / len(lines)) >= 0.4:
        return True

    return False


async def process_and_save_document(
    file_or_files: Any,
    access_group: str = "common",
    expires_at: Optional[str] = None
):
    if isinstance(file_or_files, list):
        files = file_or_files
    else:
        files = [file_or_files]

    created_docs = []

    for file in files:
        doc_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{file.filename}")

        file_bytes = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)

        doc_expires = expires_at if expires_at else "9999-12-31"

        doc_data = {
            "id": doc_id,
            "file_name": file.filename,
            "access_group": access_group,
            "expires_at": doc_expires,
            "is_deleted": False
        }
        
        supabase.table("chat_documents").insert(doc_data).execute()

        try:
            if file.filename.lower().endswith(".pdf"):
                loader = PyMuPDFLoader(file_path)
            else:
                loader = TextLoader(file_path, encoding="utf-8")
            
            loaded_docs = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len
            )
            chunks = text_splitter.split_documents(loaded_docs)

            # 💡 [핵심] 목차 청크 필터링
            valid_chunks = []
            skipped_toc_count = 0

            for chunk in chunks:
                if is_table_of_contents_chunk(chunk.page_content):
                    skipped_toc_count += 1
                    continue
                
                chunk.metadata["doc_id"] = doc_id
                chunk.metadata["source_name"] = file.filename
                chunk.metadata["expires_at"] = doc_expires
                valid_chunks.append(chunk)

            print(f"ℹ️ [목차 스킵 완료] {file.filename} -> 제외된 목차 청크: {skipped_toc_count}개")

            if valid_chunks:
                batch_size = 50
                for i in range(0, len(valid_chunks), batch_size):
                    batch_chunks = valid_chunks[i:i + batch_size]
                    vectorstore.add_documents(batch_chunks)

                print(f"✅ [VectorStore 저장 성공] {file.filename} -> 총 {len(valid_chunks)}개 순수 본문 청크 저장됨")

        except Exception as e:
            print(f"❌ [VectorStore 임베딩 저장 실패]: {e}")

        created_docs.append(doc_data)

    if not isinstance(file_or_files, list):
        return created_docs[0]["id"] if created_docs else None

    return created_docs