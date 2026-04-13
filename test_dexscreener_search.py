#!/usr/bin/env python3
"""
Test script to debug DexScreener RAG retrieval.
This directly calls the search_knowledge_base_async function to see what documents are retrieved.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'surfsense_backend'))

from app.agents.new_chat.tools.knowledge_base import search_knowledge_base_async
from app.db import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession


async def test_dexscreener_search():
    """Test DexScreener search directly."""
    
    # Get database session
    async for session in get_async_session():
        try:
            print("=" * 80)
            print("Testing DexScreener RAG Retrieval")
            print("=" * 80)
            
            # Test parameters
            user_query = "WETH price"
            search_space_id = 7
            user_id = "1951c010-436f-4636-89ca-5d86f57951df"  # admin user
            top_k = 5
            
            print(f"\nQuery: {user_query}")
            print(f"Search Space ID: {search_space_id}")
            print(f"Top K: {top_k}")
            print("\n" + "-" * 80)
            
            # Call search function
            result = await search_knowledge_base_async(
                query=user_query,
                search_space_id=search_space_id,
                user_id=user_id,
                top_k=top_k
            )
            
            print(f"\nSearch Result Type: {type(result)}")
            print(f"Result Length: {len(result) if isinstance(result, (list, dict)) else 'N/A'}")
            
            if isinstance(result, dict):
                print("\nResult Keys:", list(result.keys()))
                
                # Print sources
                if 'sources' in result:
                    sources = result['sources']
                    print(f"\nNumber of Sources: {len(sources)}")
                    
                    for i, source in enumerate(sources, 1):
                        print(f"\n--- Source {i} ---")
                        print(f"Title: {source.get('title', 'N/A')}")
                        print(f"URL: {source.get('url', 'N/A')}")
                        print(f"Type: {source.get('type', 'N/A')}")
                        print(f"Description: {source.get('description', 'N/A')[:200]}...")
                        
                        # Check for DexScreener-specific fields
                        if 'extra_fields' in source:
                            extra = source['extra_fields']
                            print(f"Extra Fields: {extra}")
                
                # Print documents
                if 'documents' in result:
                    docs = result['documents']
                    print(f"\n\nNumber of Documents: {len(docs)}")
                    
                    for i, doc in enumerate(docs[:3], 1):  # Show first 3 docs
                        print(f"\n--- Document {i} ---")
                        print(f"Type: {type(doc)}")
                        if hasattr(doc, 'page_content'):
                            print(f"Content Preview: {doc.page_content[:300]}...")
                        if hasattr(doc, 'metadata'):
                            print(f"Metadata: {doc.metadata}")
            
            elif isinstance(result, list):
                print(f"\nResult is a list with {len(result)} items")
                for i, item in enumerate(result[:3], 1):
                    print(f"\n--- Item {i} ---")
                    print(f"Type: {type(item)}")
                    print(f"Content: {str(item)[:200]}...")
            
            else:
                print(f"\nResult: {result}")
            
            print("\n" + "=" * 80)
            print("Test Complete")
            print("=" * 80)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await session.close()
            break


if __name__ == "__main__":
    asyncio.run(test_dexscreener_search())
