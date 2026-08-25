import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 1. 분할된 모든 라우터(Routers) 한 번에 임포트
from app.routers import (
    chat,
    documents,
    sessions,
    knowledge,
    auth,
    admin_users,
    admin_unanswered
)

# 2. 환경 변수 로드
load_dotenv()

# 3. FastAPI 앱 생성
app = FastAPI(
    title="Multi-User Shared RAG Backend with Supabase",
    version="1.0.0"
)

# ---------------------------------------------------------
# [디버깅 미들웨어 추가] /api/sessions 요청 헤더 및 파라미터 로깅
# ---------------------------------------------------------
@app.middleware("http")
async def log_session_requests(request: Request, call_next):
    if "/api/sessions" in request.url.path:
        print("\n==================== [API DEBUG START] ====================")
        print(f"1. [Method & Path]: {request.method} {request.url.path}")
        print(f"2. [Query Params]: {dict(request.query_params)}")
        
        # Authorization 헤더 추출
        auth_header = request.headers.get("authorization")
        print(f"3. [Authorization Header]: '{auth_header}'")
        
        # 전체 요청 헤더 확인
        print(f"4. [All Request Headers]: {dict(request.headers)}")
        print("===========================================================\n")

    response = await call_next(request)
    
    if "/api/sessions" in request.url.path:
        print(f"5. [Response Status Code]: {response.status_code}")
        print("==================== [API DEBUG END] ====================\n")
        
    return response
# ---------------------------------------------------------

# 4. CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],      # 모든 HTTP 메서드 허용
    allow_headers=["*"],      # 모든 헤더 허용
)

# 5. 라우터 등록
app.include_router(chat.router)             # POST /api/chat
app.include_router(documents.router)        # GET, POST, DELETE /api/documents
app.include_router(sessions.router)         # GET, DELETE /api/sessions
app.include_router(knowledge.router)        # GET /api/knowledge-base
app.include_router(auth.router)             # POST /api/auth/login
app.include_router(admin_users.router)      # GET, POST, DELETE /api/admin/users
app.include_router(admin_unanswered.router) # GET, PATCH, DELETE /api/admin/unanswered


# 6. 루트 엔드포인트 (서버 상태 확인용)
@app.get("/")
async def root():
    return {"message": "RAG Backend Server is Running!"}


# 7. 서버 실행 (python -m app.main 등으로 직접 실행 시)
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)