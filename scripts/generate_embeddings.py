#!/usr/bin/env python3
"""
Generate embeddings for chunks that don't have them.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client
from src.embeddings.embedder import LocalEmbedder

def main():
    # Initialize
    client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
    embedder = LocalEmbedder()
    
    print("Checking chunks without embeddings...")
    
    # Get chunks without embeddings
    result = client.table('chunks').select('id, content').is_('embedding', 'null').execute()
    chunks_without_embeddings = result.data
    
    print(f"Found {len(chunks_without_embeddings)} chunks without embeddings")
    
    if not chunks_without_embeddings:
        print("All chunks have embeddings!")
        return 0
    
    # Process in batches
    batch_size = 50
    total = len(chunks_without_embeddings)
    
    for i in range(0, total, batch_size):
        batch = chunks_without_embeddings[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}...")
        
        for chunk in batch:
            try:
                # Generate embedding
                embedding = embedder.embed_text(chunk['content'])
                embedding_list = embedding.tolist()
                
                # Update chunk with embedding
                client.table('chunks').update({
                    'embedding': embedding_list
                }).eq('id', chunk['id']).execute()
                
            except Exception as e:
                print(f"Error processing chunk {chunk['id']}: {e}")
                continue
        
        print(f"  Completed {min(i + batch_size, total)}/{total}")
    
    print("\nDone! All chunks now have embeddings.")
    
    # Verify
    result = client.table('chunks').select('id', count='exact').not_.is_('embedding', 'null').execute()
    print(f"Chunks with embeddings: {result.count}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
