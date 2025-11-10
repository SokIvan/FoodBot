import supabase
from config import SUPABASE_URL, SUPABASE_KEY

class SupabaseClient:
    def __init__(self):
        self.client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
    
    async def create_example(self, key: str, example: str):
        return self.client.table("example").insert({"key": key, "example": example}).execute()
    
    async def get_example(self, key: str):
        return self.client.table("example").select("*").eq("key", key).execute()

# Singleton instance
supabase_client = SupabaseClient()