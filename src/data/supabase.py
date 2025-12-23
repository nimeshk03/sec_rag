import os
from supabase import create_client, Client
from typing import Optional

class SupabaseClient:
    """Singleton Supabase client wrapper."""
    
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client."""
        if cls._instance is None:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            
            if not url or not key or url == "https://your-project.supabase.co":
                raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
                
            cls._instance = create_client(url, key)
            
        return cls._instance

def get_supabase() -> Client:
    """Helper function to get Supabase client."""
    return SupabaseClient.get_client()
