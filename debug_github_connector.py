#!/usr/bin/env python3
"""
Debug script to test GitHub connector indexing issues.

This script can help diagnose GitHub connector indexing problems by:
1. Checking if documents are being created in the database
2. Verifying last_indexed_at timestamp updates
3. Testing document retrieval functionality

Usage:
    python debug_github_connector.py --connector-id <id> --search-space-id <id>
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime

# Add the backend directory to Python path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'surfsense_backend')
sys.path.insert(0, backend_dir)

async def debug_github_connector(connector_id: int, search_space_id: int):
    """Debug function to test GitHub connector."""
    try:
        # Import modules
        from app.db import get_async_session, Document, SearchSourceConnector
        from sqlalchemy.future import select
        
        print(f"🔍 Debugging GitHub Connector {connector_id} in Search Space {search_space_id}")
        print("=" * 60)
        
        # Get a database session
        async with get_async_session().__aenter__() as session:
            # 1. Check if connector exists
            print("1. Checking connector existence...")
            result = await session.execute(
                select(SearchSourceConnector).filter(SearchSourceConnector.id == connector_id)
            )
            connector = result.scalars().first()
            
            if not connector:
                print(f"❌ Connector {connector_id} not found!")
                return
                
            print(f"✅ Connector found: {connector.name}")
            print(f"   Type: {connector.connector_type}")
            print(f"   Last indexed: {connector.last_indexed_at}")
            print()
            
            # 2. Check documents count
            print("2. Checking documents count...")
            result = await session.execute(
                select(Document).filter(
                    Document.search_space_id == search_space_id,
                    Document.document_type == 'GITHUB_CONNECTOR'
                )
            )
            documents = result.scalars().all()
            print(f"📄 Found {len(documents)} GitHub documents in search space {search_space_id}")
            
            if documents:
                print("   Recent documents:")
                for i, doc in enumerate(documents[:5]):  # Show first 5
                    print(f"   - {doc.title} (ID: {doc.id}, Created: {doc.created_at})")
            print()
            
            # 3. Check all documents in search space
            print("3. Checking all documents in search space...")
            result = await session.execute(
                select(Document).filter(Document.search_space_id == search_space_id)
            )
            all_documents = result.scalars().all()
            print(f"📄 Total documents in search space {search_space_id}: {len(all_documents)}")
            
            if all_documents:
                # Group by document type
                doc_types = {}
                for doc in all_documents:
                    doc_type = doc.document_type.value if hasattr(doc.document_type, 'value') else str(doc.document_type)
                    doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                
                print("   Documents by type:")
                for doc_type, count in doc_types.items():
                    print(f"   - {doc_type}: {count}")
            print()
            
            # 4. Test document retrieval query (simulate API call)
            print("4. Testing document retrieval API simulation...")
            from app.routes.documents_routes import read_documents
            from app.users import current_active_user
            
            # This is just a simulation - in real usage, you'd need proper auth
            print("   (Note: This would require proper authentication in real usage)")
            print("   The documents should be accessible via: GET /api/v1/documents?search_space_id={search_space_id}")
            
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description='Debug GitHub connector indexing issues')
    parser.add_argument('--connector-id', type=int, required=True, help='GitHub connector ID')
    parser.add_argument('--search-space-id', type=int, required=True, help='Search space ID')
    
    args = parser.parse_args()
    
    print("GitHub Connector Debug Script")
    print("============================")
    print(f"Connector ID: {args.connector_id}")
    print(f"Search Space ID: {args.search_space_id}")
    print()
    
    # Run the debug function
    try:
        asyncio.run(debug_github_connector(args.connector_id, args.search_space_id))
    except KeyboardInterrupt:
        print("❌ Script interrupted by user")
    except Exception as e:
        print(f"❌ Script failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()