from app.database import supabase

def get_allowed_access_groups(user_id: str) -> list[str]:
    # 1. user_id가 'admin'이거나 역할이 'admin'인 경우 전체 권한 부여
    if user_id == "admin":
        return ["common", "service", "service_pm", "tech_support"]

    # 2. Supabase에서 사용자의 부서(department) 및 역할(role) 조회
    user_res = supabase.table("users") \
        .select("department, user_roles(role)") \
        .eq("id", user_id) \
        .execute()

    if not user_res.data:
        # DB에 유저가 없을 경우 기본 권한만 부여
        return ["common"]

    user_data = user_res.data[0]
    dept = user_data.get("department")
    roles = [r.get("role") for r in user_data.get("user_roles", [])]

    # 'admin' 역할을 가지고 있다면 전체 권한 반환
    if "admin" in roles:
        return ["common", "service", "service_pm", "tech_support"]

    # 3. 부서/역할별 접근 가능한 access_group 매핑
    allowed = ["common"] # 공통 문서는 누구나 조회 가능
    
    if dept == "service":
        allowed.append("service")
    elif dept == "service_pm":
        allowed.extend(["service", "service_pm"])
    elif dept == "tech_support":
        allowed.extend(["service", "tech_support"])

    return list(set(allowed))