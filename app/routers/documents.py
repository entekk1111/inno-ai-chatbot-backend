from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Request
from typing import Optional, List
from app.database import supabase
from app.models.document import PermissionUpdateRequest
from app.services.document_service import process_and_save_document

router = APIRouter(prefix="/api/documents", tags=["Documents"])

def get_allowed_groups(user_id: Optional[str] = None) -> List[str]:
    # 1. 공통 접근 가능 그룹만 기본으로 설정 (tech_support 제거)
    allowed_groups = ["common"]
    
    if not user_id:
        return allowed_groups

    # 2. 관리자는 모든 그룹 조회 가능
    if user_id == "admin":
        return ["common", "admin", "tech_support", "service", "service_pm"]

    try:
        user_res = supabase.table("users").select("dept, job, role").eq("user_id", user_id).execute()
        if user_res.data:
            user_info = user_res.data[0]
            dept = user_info.get("dept") or ""
            job = user_info.get("job") or ""
            role = user_info.get("role") or ""

            # 관리자 역할(role)인 경우 전체 권한 부여
            if role == "admin":
                return ["common", "admin", "tech_support", "service", "service_pm"]

            # 3. 부서별 권한 격리 (독립 분기)
            
            # [솔루션서비스팀]
            if dept in ["service", "솔루션서비스팀", "솔루션서비스"]:
                allowed_groups.append("service")
                if job == "pm_pl":
                    allowed_groups.append("service_pm")

            # [기술지원팀]
            elif dept in ["tech_support", "기술지원팀", "기술지원"]:
                allowed_groups.append("tech_support")

    except Exception as e:
        print(f"❌ [권한 조회 오류]: {e}")

    return allowed_groups


# 1. 문서 목록 조회
@router.get("")
async def get_documents(user_id: Optional[str] = Query(None)):
    allowed_groups = get_allowed_groups(user_id)
    print(f"🔍 [get_documents] 요청 user_id: '{user_id}' | 허용 그룹: {allowed_groups}")

    # 1. file_name 컬럼으로 디버깅 출력
    try:
        raw_res = supabase.table("chat_documents").select("id, file_name, access_group, is_deleted").execute()
        print(f"🧪 [DB 전체 문서 목록 상태]: {raw_res.data}")
    except Exception as e:
        print(f"⚠️ [디버깅 출력 실패]: {e}")

    # 2. 문서 목록 조회
    res = supabase.table("chat_documents") \
        .select("*") \
        .in_("access_group", allowed_groups) \
        .eq("is_deleted", False) \
        .order("created_at", desc=True) \
        .execute()

    docs = res.data or []
    print(f"📦 [get_documents] 실제 반환 문서 개수: {len(docs)}")
    return docs


# 2. 문서 업로드 (access_group 기본값 및 디버깅 로그 추가)
@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    access_group: str = Form("common"),
    expires_at: Optional[str] = Form(None)
):
    print(f"📤 [upload_document] 업로드 시작 - 파일명: {file.filename}, access_group: {access_group}")
    
    # process_and_save_document 실행
    doc_id = await process_and_save_document(file, access_group, expires_at)
    
    print(f"✅ [upload_document] 업로드 완료 - 생성된 ID: {doc_id}")
    return {"ok": True, "document_id": doc_id, "message": "문서 업로드 완료"}


# 3. 문서 정보/권한 수정 (PATCH - 누락되었던 엔드포인트 추가)
@router.patch("/{document_id}")
async def update_document(
    document_id: str,
    request: Request
):
    try:
        print(f"✏️ [update_document] 수정 요청 document_id: {document_id}")
        
        # 프론트엔드에서 전송된 JSON 바디 수신
        body_data = await request.json()
        print(f"📝 [update_document] 수신 데이터: {body_data}")

        if not body_data:
            return {"ok": True, "message": "수정할 항목이 없습니다."}

        # Supabase DB 업데이트
        res = supabase.table("chat_documents") \
            .update(body_data) \
            .eq("id", document_id) \
            .execute()

        return {"ok": True, "message": "문서 정보가 성공적으로 수정되었습니다.", "data": res.data}
    except Exception as e:
        print(f"❌ [update_document 오류]: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 4. 문서 삭제 (DELETE)
@router.delete("/{document_id}")
async def delete_document(document_id: str):
    try:
        print(f"🗑️ [delete_document] 삭제 요청 document_id: {document_id}")

        # 1. 문서 존재 여부 확인
        check_res = supabase.table("chat_documents") \
            .select("id") \
            .eq("id", document_id) \
            .execute()

        if not check_res.data:
            print(f"❌ [delete_document] DB에서 해당 ID를 찾지 못함: {document_id}")
            raise HTTPException(status_code=404, detail="해당 문서를 찾을 수 없습니다.")

        # 2. 소프트 삭제 수행 (is_deleted = True)
        res = supabase.table("chat_documents") \
            .update({"is_deleted": True}) \
            .eq("id", document_id) \
            .execute()

        return {"ok": True, "message": "문서가 성공적으로 삭제되었습니다.", "deleted_id": document_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ [delete_document 오류]: {e}")
        raise HTTPException(status_code=500, detail=str(e))