import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class SupabaseClient:
    def __init__(self):
        self.client: Client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
    
    # Users methods
    async def get_users(self):
        return self.client.table("users").select("*").execute()

    async def get_user(self, id):
        return self.client.table("users").select("*").eq("id", id).execute()
    
    async def set_user(self, data):
        return self.client.table("users").insert(data).execute()   

    async def update_user(self, data):
        return self.client.table("users").update(data).eq("id", data["id"]).execute()
    
    async def user_exists(self, user_id):
        """Проверяет существует ли пользователь"""
        response = await self.get_user(user_id)
        return len(response.data) > 0
    
    # Food methods
    async def add_food_review(self, data):
        existing = await self.get_food_review(data["user_id"], data["date"], data["name"])
        if existing.data:
            return await self.update_food_review(data)
        return await self.set_food_review(data)
    
    async def set_food_review(self, data):
        return self.client.table("food").insert(data).execute()
    
    async def get_food_review(self, user_id, date, name):
        return self.client.table("food").select("*").eq("user_id", user_id).eq("date", date).eq("name", name).execute()
    
    async def update_food_review(self, data):
        return self.client.table("food").update(data).eq("user_id", data["user_id"]).eq("date", data["date"]).eq("name", data["name"]).execute()
    
    async def get_food_reviews_by_name(self, name):
        return self.client.table("food").select("*").eq("name", name).execute()
    
    async def get_food_reviews_by_user(self, user_id):
        return self.client.table("food").select("*").eq("user_id", user_id).execute()
    
    async def get_all_food_reviews(self):
        return self.client.table("food").select("*").execute()
    
    # Food menu methods
    async def add_food_menu_review(self, data):
        existing = await self.get_food_menu_review(data["user_id"], data["date"], data["type"])
        if existing.data:
            return await self.update_food_menu_review(data)
        return await self.set_food_menu_review(data)
    
    async def set_food_menu_review(self, data):
        return self.client.table("food_menu").insert(data).execute()
    
    async def get_food_menu_review(self, user_id, date, menu_type):
        return self.client.table("food_menu").select("*").eq("user_id", user_id).eq("date", date).eq("type", menu_type).execute()
    
    async def update_food_menu_review(self, data):
        return self.client.table("food_menu").update(data).eq("user_id", data["user_id"]).eq("date", data["date"]).eq("type", data["type"]).execute()
    
    async def get_food_menu_reviews_by_type(self, menu_type):
        return self.client.table("food_menu").select("*").eq("type", menu_type).execute()
    
    async def get_food_menu_reviews_by_user(self, user_id):
        return self.client.table("food_menu").select("*").eq("user_id", user_id).execute()
    
    async def get_all_food_menu_reviews(self):
        return self.client.table("food_menu").select("*").execute()

supabase_client = SupabaseClient()