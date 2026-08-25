from fastapi import APIRouter, HTTPException, Depends
from app.models import LoginRequest
from app.security import verify_password, create_access_token # create_access_token 추가
from app.database import supabase # Supabase client 인스턴스
from app.models.auth import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/login")
def login(body: LoginRequest):
    res = supabase.table("users").select("*").eq("user_id", body.user_id).execute()
    
    if not res.data:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    
    user = res.data[0]
    if not verify_password(body.password, user["password"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    
    # 1. JWT 토큰 생성
    access_token = create_access_token(data={"sub": user["user_id"], "role": user.get("role", "user")})
    
    # 2. 응답에 token(또는 access_token) 포함하여 반환
    return {
        "ok": True,
        "token": access_token,  # <--- 이 부분이 추가되어야 프론트가 저장할 수 있습니다.
        "user": {
            "user_id": user["user_id"],
            "name": user["name"],
            "dept": user["dept"],
            "position": user["position"],
            "role": user.get("role", "user")
        }
    }