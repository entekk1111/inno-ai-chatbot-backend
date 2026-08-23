from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL과 SUPABASE_KEY가 .env 파일에 설정되어야 합니다.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)