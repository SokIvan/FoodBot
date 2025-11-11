import os
from supabase import create_client, Client

from dotenv import load_dotenv

load_dotenv()

class SupabaseClient:
    def __init__(self):
        self.client: Client = create_client(supabase_url=os.getenv("SUPABASE_URL"),supabase_key=os.getenv("SUPABASE_KEY"))
        
    async def get_users(self):
        return await self.client.table("users").select("*").execute()

    async def get_user(self, id):
        return await self.client.table("users").select("*").eq("id",id).execute()
    
    async def set_user(self, data):
        return await self.client.table("users").insert(data).execute()   

    async def update_user(self,data):
        return await self.client.table("users").update(data).execute()
    
    
    
    async def add_food_review(self,data):
        if await self.get_food_review(data):
            return await self.update_food_review(data)
        return await self.set_food_menu_review(data)
    
    async def set_food_review(self,data):
        return await self.client.table("food").insert(data).execute()
        
    async def get_food_review(self,data):
        return await self.client.table("food").select("*").eq("name",data["name"]).eq("date",data["date"]).eq("user_id",data["id"]).execute()
    
    async def update_food_review(self,data):
        return await self.client.table("food").update(data).eq("name",data["name"]).eq("date",data["date"]).eq("user_id",data["id"]).execute()
        
    async def get_food_reviews(self,name):
        return await self.client.table("food").select("*").eq("name",name).execute()
    async def get_food_reviews(self,id):
        return await self.client.table("food").select("*").eq("user_id",id).execute()
    async def get_food_reviews(self,):
        return await self.client.table("food").select("*").execute()
    
    
    async def set_food_menu_review(self,data):
        pass
    async def get_food_menu_reviews(self,name):
        pass
    async def get_food_menu_reviews(self,id):
        pass
    async def get_food_menu_reviews(self,):
        pass



supabase_client = SupabaseClient()
