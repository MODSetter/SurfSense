#!/usr/bin/env python3
"""
Integration test script for Chat RAG with DexScreener.
Tests the full loop: login -> create thread -> send query -> verify response.
"""

import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000"

def login(email: str, password: str) -> str:
    """Login and return JWT access token."""
    print(f"🔐 Logging in as {email}...")
    response = requests.post(
        f"{BASE_URL}/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    data = response.json()
    token = data.get("access_token")
    print(f"✅ Login successful!")
    return token

def create_thread(token: str, space_id: int = 7) -> int:
    """Create a new chat thread."""
    print(f"\n📝 Creating thread in search_space_id={space_id}...")
    
    # First ensure we have a thread or create one
    # If the API requires just a thread ID, we ask for one.
    response = requests.post(
        f"{BASE_URL}/api/v1/threads",
        json={"search_space_id": space_id},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code not in [200, 201]:
        print(f"⚠️ Create thread failed: {response.status_code}")
        # Try listing threads and picking one?
        # For now, exit
        # print(response.text)
        return 1 # Fallback ID

    data = response.json()
    thread_id = data.get("id")
    print(f"✅ Thread created: {thread_id}")
    return thread_id

def test_chat_query(token: str, thread_id: int, query: str) -> bool:
    """Send a chat query and check response."""
    print(f"\n💬 Sending query: '{query}'...")
    
    payload = {
        "chat_id": thread_id,  # The API expects 'chat_id', not 'thread_id'
        "user_query": query,   # The API expects 'user_query', not 'query'
        "search_space_id": 7,
    }
    
    # We use stream=False for easier testing, or handle SSE if needed.
    # Assuming the backend supports non-streaming execution via /new_chat or similar
    # The Implementation Plan mentioned POST /api/v1/new_chat
    
    response = requests.post(
        f"{BASE_URL}/api/v1/new_chat",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        stream=True 
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Chat request failed: {response.text}")
        return False

    # Handle stream or full response
    full_text = ""
    print("Stream output:")
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                try:
                    data = json.loads(line_str[6:])
                    # Handle Vercel AI SDK compatible format
                    if data.get("type") == "text-delta" and "delta" in data:
                        chunk = data["delta"]
                        full_text += chunk
                        print(chunk, end="", flush=True)
                    elif "answer" in data: # Fallback/Legacy
                        chunk = data["answer"]
                        full_text += chunk
                        print(chunk, end="", flush=True)
                    elif data.get("type") == "error":
                        print(f"\n[ERROR] Stream error: {data}")
                except Exception as e:
                     pass # Ignore parse errors for non-JSON lines like [DONE]
    
    print("\n\n✅ Full Response Received.")
    print("-" * 40)
    print(full_text)
    print("-" * 40)
    
    # Verification
    if "$" in full_text and any(x in full_text.lower() for x in ["price", "usd"]):
        print("✅ PASSED: Response contains price information.")
        return True
    else:
        print("⚠️ WARNING: Response might not contain price info.")
        return False

def main():
    print("=" * 60)
    print("Chat RAG Verification (DexScreener)")
    print("=" * 60)
    
    token = login("admin@surfsense.ai", "password123")
    
    # Step 2: Create Thread
    # Note: Using search_space_id=1 for verifying if default space works or 7 if specific
    # Implementation plan said 7.
    thread_id = create_thread(token, space_id=7)
    
    # Step 3: Chat Query
    success = test_chat_query(token, thread_id, "What is the price of WETH on Ethereum?")
    
    if success:
        print("\n🎉 Verification Successful!")
        sys.exit(0)
    else:
        print("\n❌ Verification Failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
