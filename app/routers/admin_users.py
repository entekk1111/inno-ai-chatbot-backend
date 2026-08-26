from fastapi import APIRouter, HTTPException, status
from typing import Optional
from app.database import supabase
from app.models.user import UserCreate, UserUpdate
from app.security import get_password_hash  # ★ 비밀번호 암호화 함수

router = APIRouter(prefix="/api/admin/users", tags=["Admin Users"])

# 1. 사용자 목록 조회 (created_at 내림차순 정렬 추가)
@router.get("")
async def get_users():
    try:
        # created_at 기준 desc=True 정렬 -> 생성된 순서대로 맨 위에 표시됨
        res = (
            supabase.table("users")
            .select("user_id, name, dept, role, job, created_at")
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"❌ [User List Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 2. 사용자 생성 (신규 등록)
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate):
    try:
        user_data = user.model_dump()
        
        # position 빈값 방지
        if user_data.get("position") is None:
            user_data["position"] = ""

        # 평문 비밀번호 bcrypt 암호화
        if "password" in user_data and user_data["password"]:
            user_data["password"] = get_password_hash(user_data["password"])

        res = supabase.table("users").insert(user_data).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        print(f"❌ [User Create Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 3. 사용자 정보 수정 (수정 시 created_at은 변경되지 않아 기존 위치 유지)
@router.patch("/{user_id}")
async def update_user(user_id: str, user: UserUpdate):
    try:
        update_data = user.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="수정할 정보가 없습니다.")
        
        # 비밀번호 수정 시에도 bcrypt 해시 암호화 적용
        if "password" in update_data and update_data["password"]:
            update_data["password"] = get_password_hash(update_data["password"])

        # created_at 필드는 업데이트 대상에서 제외 (위치 변경 방지)
        update_data.pop("created_at", None)

        res = supabase.table("users").update(update_data).eq("user_id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        return res.data[0]
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ [User Update Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 4. 사용자 삭제
@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(user_id: str):
    try:
        # 1. 사용자 존재 여부 확인
        check_res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        if not check_res.data:
            raise HTTPException(status_code=404, detail="해당 사용자를 찾을 수 없습니다.")

        # 2. DB에서 사용자 삭제
        supabase.table("users").delete().eq("user_id", user_id).execute()
        
        return {
            "message": f"사용자 '{user_id}'가 성공적으로 삭제되었습니다.",
            "deleted_user_id": user_id
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ [User Delete Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))