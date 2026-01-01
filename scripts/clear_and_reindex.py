#!/usr/bin/env python3
"""
Clear existing filings and re-index fresh data.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.store import SupabaseStore

def main():
    store = SupabaseStore()
    
    print("Checking current database state...")
    
    # Check filings
    filings = store.client.table('filings').select('*').execute()
    print(f"Current filings: {len(filings.data)}")
    
    # Check chunks
    chunks = store.client.table('chunks').select('id', count='exact').execute()
    print(f"Current chunks: {chunks.count}")
    
    if len(filings.data) > 0:
        print("\nClearing existing filings and chunks...")
        
        # Delete all chunks first (foreign key constraint)
        store.client.table('chunks').delete().neq('id', 0).execute()
        print("✓ Deleted all chunks")
        
        # Delete all filings
        store.client.table('filings').delete().neq('id', 0).execute()
        print("✓ Deleted all filings")
        
        print("\nDatabase cleared. Now run:")
        print("podman exec rag-safety-api python3 scripts/populate_data.py --tickers MSFT")
    else:
        print("\nNo filings to clear.")

if __name__ == "__main__":
    main()
