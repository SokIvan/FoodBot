import os
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

class SupabaseClient:
    def __init__(self):
        # Простая инициализация без лишних параметров
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    async def create_example(self, key: str, example: str):
        try:
            return self.client.table("example").insert({"key": key, "example": example}).execute()
        except Exception as e:
            print(f"Supabase error: {e}")
            return None
    
    async def get_example(self, key: str):
        try:
            return self.client.table("example").select("*").eq("key", key).execute()
        except Exception as e:
            print(f"Supabase error: {e}")
            return None

# Singleton instance
supabase_client = SupabaseClient()