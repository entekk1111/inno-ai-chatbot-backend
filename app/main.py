import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 1. 환경 변수 로드
load_dotenv()

# 2. FastAPI 앱 생성
app = FastAPI(
    title="Multi-User Shared RAG Backend with Supabase",
    version="1.0.0"
)

# 3. CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],      # 모든 HTTP 메서드 허용
    allow_headers=["*"],      # 모든 헤더 허용
)

# 4. 분할된 라우터(Routers) 임포트 및 등록
from app.routers import chat, documents, sessions, knowledge

app.include_router(chat.router)         # POST /api/chat
app.include_router(documents.router)    # GET, POST, DELETE /api/documents
app.include_router(sessions.router)     # GET, DELETE /api/sessions
app.include_router(knowledge.router)    # GET /api/knowledge-base


# 5. 루트 엔드포인트 (서버 상태 확인용)
@app.get("/")
async def root():
    return {"message": "RAG Backend Server is Running!"}


# 6. 서버 실행 (직접 실행 시)
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)