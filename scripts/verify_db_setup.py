import os
import sys
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.supabase import get_supabase

def verify_setup():
    """Verify Supabase connection and schema setup."""
    print("Verifying Supabase setup...")
    
    # 1. Check environment variables
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or "your-project" in url:
        print("Error: SUPABASE_URL not configured in .env")
        return False
    
    if not key or "your-anon-key" in key:
        print("Error: SUPABASE_KEY not configured in .env")
        return False
        
    print("Environment variables found")
    
    try:
        # 2. Test Connection
        client = get_supabase()
        print("Client initialized")
        
        # 3. Test Schema (call an RPC function)
        print("Testing database connection and schema...")
        try:
            # Try to call get_cache_stats which we defined in schema.sql
            response = client.rpc("get_cache_stats", {}).execute()
            print("RPC 'get_cache_stats' call successful")
            print(f"   Stats: {response.data}")
        except Exception as e:
            print(f"Error calling RPC function: {e}")
            print("   (Did you run scripts/schema.sql in the Supabase SQL Editor?)")
            return False
            
        # 4. Check Tables (try simple select)
        tables = ["filings", "chunks", "cache", "safety_logs", "earnings_calendar"]
        for table in tables:
            try:
                client.table(table).select("count", count="exact").limit(0).execute()
                print(f"Table '{table}' exists")
            except Exception as e:
                print(f"Error checking table '{table}': {e}")
                return False
                
        print("\nSupabase setup verified successfully!")
        return True
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = verify_setup()
    sys.exit(0 if success else 1)
